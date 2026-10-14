"""Orquesta: servidor de desarrollo → navegador → login → captura → escena → postproducción."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from . import capture as cap_mod
from . import post
from .demo import Demo, completar_ruta
from .voice import Voice

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = (Path(__file__).parent / "overlay.js").read_text(encoding="utf-8")
OFUSCAR_JS = (Path(__file__).parent / "ofuscar.js").read_text(encoding="utf-8")
OFUSCAR_DEFECTO = {"emails": True, "telefonos": True, "documentos": True, "cuenta": True,
                   "textos": [], "selectores": [], "blur": 9}


CUENTAS = ("organizador", "delegado", "jugador", "veedor")


def cuenta_env(scene_mod) -> dict:
    """Las variables de entorno con la cuenta de la escena como DEMO_EMAIL y
    DEMO_PASSWORD: CUENTA = "delegado" entra con DEMO_DELEGADO_EMAIL y
    DEMO_DELEGADO_PASSWORD. Sin CUENTA (u "organizador"), la de siempre."""
    cuenta = (getattr(scene_mod, "CUENTA", "") or "").lower()
    env = dict(os.environ)
    if cuenta and cuenta != "organizador":
        pref = f"DEMO_{cuenta.upper()}_"
        if not (env.get(pref + "EMAIL") and env.get(pref + "PASSWORD")):
            raise SystemExit(f"ERROR: la escena entra como {cuenta!r}: faltan {pref}EMAIL y "
                             f"{pref}PASSWORD en tu .env (ver .env.example).")
        env["DEMO_EMAIL"], env["DEMO_PASSWORD"] = env[pref + "EMAIL"], env[pref + "PASSWORD"]
    return env


def ofuscar_js(cfg: dict, datos: dict, env=os.environ) -> str | None:
    """Script que blurea los datos sensibles (ver OFUSCAR en config.py)."""
    o = {**OFUSCAR_DEFECTO, **(cfg.get("OFUSCAR") or {})}
    if o.get("activo") is False:
        return None
    textos = list(o.get("textos") or [])
    if o.get("cuenta"):   # nombre y email de la cuenta con la que se graba
        textos += list(datos.get("sensibles") or []) + [env.get("DEMO_EMAIL", "")]
    conf = {k: o[k] for k in ("emails", "telefonos", "documentos", "selectores", "blur")}
    conf["textos"] = [t.strip() for t in textos if t and len(t.strip()) >= 3]
    return OFUSCAR_JS.replace("__CONFIG__", json.dumps(conf, ensure_ascii=False))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def list_scenes(scenes_dir: Path) -> dict[str, Path]:
    return {p.stem: p for p in sorted(scenes_dir.glob("*.py")) if not p.stem.startswith("_")}


# ---------------------------------------------------------------------- #
def _commit() -> str:
    """Commit del grabador, con "+cambios" si lo que afecta al video no está
    commiteado: ata cada video a la versión de la escena que lo generó."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", check=True).stdout.strip()
    try:
        sha = git("rev-parse", "--short", "HEAD")
        dirty = git("status", "--porcelain", "--", "escenas", "recorder", "config.py",
                    "fonts", "musica")
        return sha + ("+cambios" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "sin git"


def _up(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=2)
        return True
    except Exception as e:
        return hasattr(e, "code")  # respondió (aunque sea 404): el servidor está arriba


def _stop_tree(proc: subprocess.Popen) -> None:
    """Apaga el servidor con sus hijos (npm → node → vite), no solo el shell."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)   # start_new_session: pgid == pid
    except ProcessLookupError:
        pass


class DevServer:
    """Arranca tu `npm run dev` si la app no responde, y lo apaga al final.

    `cmd` puede ser un texto (se ejecuta en el shell del sistema) o una lista
    de argumentos (sin shell: no hay que preocuparse por espacios en rutas).
    """

    def __init__(self, url: str, spec: dict | None):
        self.url, self.spec, self.proc = url, spec, None

    def __enter__(self):
        if _up(self.url):
            return self
        if not self.spec:
            raise SystemExit(f"ERROR: {self.url} no responde. Levantá la app (npm run dev), "
                             "revisá APP_URL en tu .env o definí APP_DIR y APP_DEV_CMD "
                             "para que arranque sola.")
        cmd = self.spec["cmd"]
        cwd = Path(self.spec.get("cwd") or ".").expanduser()
        print(f"→ Levantando la app: {cmd}  (en {cwd})")
        self.proc = subprocess.Popen(cmd, shell=isinstance(cmd, str), cwd=cwd,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     start_new_session=True)
        for _ in range(120):
            if _up(self.url):
                time.sleep(1.0)
                return self
            if self.proc.poll() is not None:
                raise SystemExit("ERROR: el servidor de desarrollo terminó al arrancar.")
            time.sleep(0.5)
        raise SystemExit(f"ERROR: {self.url} no respondió en 60 s.")

    def __exit__(self, *a):
        if self.proc and self.proc.poll() is None:
            _stop_tree(self.proc)


# ---------------------------------------------------------------------- #
def context_options(p, prof: dict, cfg: dict) -> dict:
    if prof.get("device"):
        opts = dict(p.devices[prof["device"]])
        opts.pop("default_browser_type", None)
    else:
        opts = {"viewport": prof["viewport"], "is_mobile": False, "has_touch": False}
    if "viewport" in prof:
        opts["viewport"] = prof["viewport"]
    opts["device_scale_factor"] = prof.get("scale", opts.get("device_scale_factor", 1))
    opts.update(
        locale=cfg.get("LOCALE", "es-AR"),
        timezone_id=cfg.get("TIMEZONE", "America/Argentina/Buenos_Aires"),
        color_scheme=cfg.get("COLOR_SCHEME", "light"),
        service_workers=cfg.get("SERVICE_WORKERS", "allow"),
        ignore_https_errors=True,
    )
    return opts


async def record_one(browser, p, cfg: dict, scene_mod, scene_name: str, profile: str,
                     voice: Voice, work: Path, headed: bool) -> None:
    prof = cfg["PROFILES"][profile]
    opts = context_options(p, prof, cfg)
    mobile = bool(opts.get("is_mobile"))
    ctx = await browser.new_context(**opts)
    overlay = (OVERLAY.replace("__MODE__", "touch" if mobile else "mouse")
               .replace("__ACCENT__", cfg.get("ACCENT", "#4F7CFF")))
    await ctx.add_init_script(overlay)
    page = await ctx.new_page()
    base = cfg["BASE_URL"].rstrip("/")

    try:
        # 1) Login fuera de cámara: la captura aún no empezó. Lo que devuelve
        #    (ej. {"liga": "…"}) completa las rutas de la escena: "/league/{liga}/…".
        datos = {}
        env = cuenta_env(scene_mod)
        if getattr(scene_mod, "LOGIN", True) and cfg.get("login"):
            datos = await cfg["login"](page, base, env) or {}
        # Desde la próxima carga, los datos sensibles se blurean antes de capturarse.
        if script := ofuscar_js(cfg, datos, env):
            await ctx.add_init_script(script)

        # 2) Página inicial de la escena.
        d = Demo(page, profile=profile, mobile=mobile, base_url=base, voice=voice,
                 pace=cfg.get("PACE", 1.0), gap=cfg.get("VOICE_GAP", 0.35), datos=datos)
        await d.goto(getattr(scene_mod, "START", "/"))
        if hasattr(scene_mod, "prepare"):
            await scene_mod.prepare(d)       # ajustes previos, también fuera de cámara

        # 3) Grabación.
        vp = opts["viewport"]
        scale = opts["device_scale_factor"]
        mode = prof.get("capture") or ("screencast" if scale == 1 else "screenshot")
        work.mkdir(parents=True, exist_ok=True)
        cap = cap_mod.Capture(page, ctx, work / "raw.mp4", mode=mode, width=vp["width"],
                              height=vp["height"], scale=scale, mobile=mobile,
                              quality=cfg.get("JPEG_QUALITY", 85))
        d.input_lock = cap.input_lock
        d.t0 = await cap.start()
        d.events = []   # lo de prepare() no se ve: el zoom solo sigue lo que se grabó
        await asyncio.sleep(cfg.get("LEAD_IN", 0.6))
        try:
            await scene_mod.run(d)
            await asyncio.sleep(cfg.get("TAIL", 1.2))
        finally:
            await d._voice_free.wait()
            t_end = await cap.stop()
            # 4) Fuera de cámara otra vez: deshacer lo que la toma creó y no
            #    se puede borrar antes de la próxima. Corre aunque run() falle.
            if hasattr(scene_mod, "cleanup"):
                try:
                    await scene_mod.cleanup(d)
                except Exception as e:
                    print(f"   AVISO: cleanup() de la escena falló: {e}")
        elapsed = t_end - d.t0
        fps_in = cap.frames_in / elapsed if elapsed else 0
        print(f"   {elapsed:.1f} s grabados · {cap.frames_in} cuadros ({fps_in:.0f}/s, modo {mode})")
        if fps_in < 12:
            print("   AVISO: pocos cuadros por segundo; el video puede verse entrecortado. "
                  "Probá scale 1.5 en el perfil o cerrá otras apps.")

        (work / "timeline.json").write_text(json.dumps({
            "scene": scene_name, "profile": profile, "trim_start": 0.0,
            "timeline": d.timeline,
            "events": d.events, "viewport": vp,   # para el zoom de postproducción
            # Con qué se grabó: postproducción lo deja junto al video (.json).
            "grabacion": {
                "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
                "commit": _commit(),
                "escena_sha1": hashlib.sha1(Path(scene_mod.__file__).read_bytes()).hexdigest()[:12],
                "app": base,
                "sistema": platform.platform(),
                "chromium": browser.version,
                "voz": f"{voice.provider}:{voice.voice}",
                "cps": round(fps_in, 1),
            },
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    finally:
        await ctx.close()


async def run(cfg: dict, scenes: list[str], profiles: list[str], *, headed: bool,
              remix_only: bool, music_override, webm: bool, voice_override: str | None) -> None:
    from playwright.async_api import async_playwright

    vcfg = dict(cfg["VOICE"])
    if voice_override:
        vcfg["voice"] = voice_override
    voice = Voice(vcfg)
    scenes_dir = cfg["_SCENES_DIR"]
    out_root = cfg["_OUTPUT_DIR"]
    available = list_scenes(scenes_dir)

    if music_override is False:
        music_cfg = {**cfg["MUSIC"], "file": None}
    elif music_override:
        music_cfg = {**cfg["MUSIC"], "file": music_override}
    else:
        music_cfg = cfg["MUSIC"]

    results = []

    async def record_all():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not headed,
                                              slow_mo=150 if headed else 0)
            try:
                for name in scenes:
                    mod = load_module(available[name], f"escena_{name}")
                    wanted = [pr for pr in profiles if pr in getattr(mod, "PROFILES", profiles)]
                    for prof in wanted:
                        print(f"● {name} [{prof}] grabando…")
                        await record_one(browser, p, cfg, mod, name, prof, voice,
                                         out_root / name / ".work" / prof, headed)
            finally:
                await browser.close()

    if not remix_only:
        with DevServer(cfg["BASE_URL"], cfg.get("DEV_SERVER")):
            await record_all()

    for name in scenes:
        mod = load_module(available[name], f"escena_{name}")
        title = getattr(mod, "TITLE", name)
        out_dir = out_root / name
        done = []
        for prof in profiles:
            work = out_dir / ".work" / prof
            if not (work / "timeline.json").is_file():
                if remix_only:
                    print(f"   (sin grabación previa de {name} [{prof}], se omite)")
                continue
            print(f"● {name} [{prof}] postproducción…")
            music = post.pick_music(music_cfg)
            o = await asyncio.to_thread(post.render, work, out_dir, name,
                                        {**cfg, "MUSIC": music_cfg,
                                         # la escena puede ajustar sus animaciones
                                         "ANIMACIONES": {**(cfg.get("ANIMACIONES") or {}),
                                                         **getattr(mod, "ANIMACIONES", {})}},
                                        music, webm, title)
            done.append(prof)
            results.append((name, prof, o, music))
        if done:
            all_profiles = [pr for pr in cfg["PROFILES"] if (out_dir / f"{name}-{pr}.mp4").is_file()]
            post.write_snippet(out_dir, name, title, all_profiles)
        if not cfg.get("KEEP_WORK", True):
            shutil.rmtree(out_dir / ".work", ignore_errors=True)

    if results:
        print("\nListo:")
        for name, prof, o, music in results:
            mb = o["video"].stat().st_size / 1e6
            w, h = o["size"]
            extra = f" · música: {music.name}" if music else ""
            print(f"  {o['video'].relative_to(ROOT)}  {w}x{h} · {o['duration']:.1f} s · {mb:.1f} MB{extra}")
            if "video_subs" in o:
                print(f"  {o['video_subs'].relative_to(ROOT)}  (subtítulos quemados)")


# ---------------------------------------------------------------------- #
# Inspección: para escribir escenas sin tener el código de la app.
_INSPECT_JS = """() => {
  const sel = '[data-testid],button,a[href],input,select,textarea,label,' +
              '[role=button],[role=tab],[role=link],[role=checkbox],[role=switch],[role=menuitem]';
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    if (!r.width || !r.height || s.visibility === 'hidden' || s.display === 'none') continue;
    out.push({
      testid: el.getAttribute('data-testid') || '',
      id: el.id || '',
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      aria: el.getAttribute('aria-label') || '',
      placeholder: el.getAttribute('placeholder') || '',
      name: el.getAttribute('name') || '',
      text: (el.innerText || el.value || '').trim().replace(/\\s+/g, ' ').slice(0, 60),
    });
  }
  return out;
}"""


def _suggest(el: dict) -> str:
    """El selector más estable disponible, en el orden que pide la skill."""
    q = lambda v: v.replace("'", "\\'")  # noqa: E731
    if el["testid"]:
        return f"[data-testid={el['testid']}]"
    if el["id"] and not re.search(r"\d{3,}|:", el["id"]):   # ids generados: no
        return f"#{el['id']}"
    if el["tag"] in ("input", "select", "textarea"):
        if el["name"]:
            return f"{el['tag']}[name={el['name']}]"
        if el["placeholder"]:
            return f"[placeholder='{q(el['placeholder'])}']"
    name = el["aria"] or el["text"]
    role = el["role"] or {"button": "button", "a": "link"}.get(el["tag"], "")
    if role and name:
        return f"role={role}[name='{q(name)}']"
    if el["aria"]:
        return f"[aria-label='{q(el['aria'])}']"
    if el["text"]:
        return f"text={el['text']}"
    return el["tag"]


async def inspect_route(cfg: dict, route: str, profiles: list[str], headed: bool) -> None:
    """Hace login, abre `route` y lista los elementos con los que se puede
    interactuar, con el selector sugerido y una captura de pantalla."""
    from playwright.async_api import async_playwright

    out_dir = cfg["_OUTPUT_DIR"] / "_inspeccion"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w]+", "-", route).strip("-") or "inicio"
    base = cfg["BASE_URL"].rstrip("/")

    with DevServer(cfg["BASE_URL"], cfg.get("DEV_SERVER")):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not headed)
            try:
                for profile in profiles:
                    ctx = await browser.new_context(**context_options(p, cfg["PROFILES"][profile], cfg))
                    page = await ctx.new_page()
                    datos = {}
                    if cfg.get("login"):
                        datos = await cfg["login"](page, base, os.environ) or {}
                    ruta = completar_ruta(route, datos)
                    await page.goto(ruta if ruta.startswith("http") else base + ruta,
                                    wait_until="domcontentloaded")
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    items = await page.evaluate(_INSPECT_JS)
                    shot = out_dir / f"{slug}-{profile}.png"
                    await page.screenshot(path=str(shot), full_page=True)
                    await ctx.close()

                    print(f"\n● {route} [{profile}] · {len(items)} elementos · URL final: {page.url}")
                    for el in items:
                        text = el["text"] if el["text"] and el["text"] not in _suggest(el) else ""
                        print(f"  {_suggest(el):50s} {el['tag']:8s} {text}")
                    print(f"  Captura: {shot.relative_to(ROOT) if shot.is_relative_to(ROOT) else shot}")
            finally:
                await browser.close()
