#!/usr/bin/env python3
"""
Graba demos de tu PWA con voz, subtítulos y música, en celular y escritorio.

  uv run grabar.py                        todas las escenas, ambos perfiles
  uv run grabar.py crear_tarea            solo una escena (o varias)
  uv run grabar.py --perfil mobile        solo celular
  uv run grabar.py --listar               app configurada y escenas disponibles
  uv run grabar.py --inspeccionar /ruta   elementos de una pantalla, para escribir escenas
  uv run grabar.py --ver                  abre el navegador para depurar
  uv run grabar.py --remezclar            rehace audio/subtítulos sin regrabar
  uv run grabar.py crear_tarea --hoja     hoja de cuadros para revisar el video
  uv run grabar.py --musica musica/x.mp3 | --sin-musica
  uv run grabar.py --voz es-AR-TomasNeural
  uv run grabar.py --voz-prueba           tono en vez de voz (sin internet)
  uv run --extra azure grabar.py --proveedor-voz azure   voz oficial, para los finales
  uv run grabar.py --config ejemplo/config.py   prueba con la app de ejemplo
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from recorder import utf8_console  # noqa: E402

utf8_console()
try:
    import dotenv  # noqa: F401
    import playwright  # noqa: F401
except ImportError:
    sys.exit("ERROR: faltan dependencias. Ejecutá siempre con uv:  uv run grabar.py …\n"
             "(la primera vez:  uv run instalar.py)")

from recorder import post, runner  # noqa: E402


def load_config(path: Path) -> dict:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    load_dotenv(path.parent / ".env")
    mod = runner.load_module(path, "demo_config")
    cfg = {k: getattr(mod, k) for k in dir(mod) if not k.startswith("__")}
    base = path.parent
    cfg["_SCENES_DIR"] = (base / cfg.get("SCENES_DIR", "escenas")).resolve()
    cfg["_OUTPUT_DIR"] = (ROOT / cfg.get("OUTPUT_DIR", "salida")).resolve()
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(description="Grabador de demos para la landing.")
    ap.add_argument("escenas", nargs="*", help="nombres de escena (archivo sin .py)")
    ap.add_argument("--perfil", choices=["mobile", "desktop", "reel", "todos"], default="todos")
    ap.add_argument("--config", default=str(ROOT / "config.py"))
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--inspeccionar", metavar="RUTA",
                    help="lista los elementos de esa pantalla con su selector sugerido")
    ap.add_argument("--ver", action="store_true", help="navegador visible (depurar)")
    ap.add_argument("--remezclar", action="store_true", help="solo postproducción")
    ap.add_argument("--hoja", action="store_true",
                    help="genera hojas de cuadros de videos ya grabados, para revisarlos")
    ap.add_argument("--musica", help="archivo de música o 'auto'")
    ap.add_argument("--sin-musica", action="store_true")
    ap.add_argument("--voz", help="voz de edge-tts, ej. es-AR-ElenaNeural")
    ap.add_argument("--voz-prueba", action="store_true",
                    help="tono en lugar de voz (sin internet), para probar rápido")
    ap.add_argument("--proveedor-voz", choices=["edge", "azure", "test"],
                    help="edge para borradores; azure para los finales (uv run --extra azure …)")
    ap.add_argument("--webm", action="store_true", help="además exporta .webm (VP9)")
    a = ap.parse_args()

    cfg = load_config(Path(a.config).resolve())
    if a.proveedor_voz or a.voz_prueba:
        cfg["VOICE"] = {**cfg["VOICE"], "provider": "test" if a.voz_prueba else a.proveedor_voz}
    available = runner.list_scenes(cfg["_SCENES_DIR"])
    profiles = list(cfg["PROFILES"]) if a.perfil == "todos" else [a.perfil]

    if a.inspeccionar:
        asyncio.run(runner.inspect_route(cfg, a.inspeccionar, profiles, headed=a.ver))
        return

    if a.listar:
        app_dir = cfg.get("APP_DIR")
        print(f"App:     {cfg['BASE_URL']}")
        print(f"Código:  {os.path.expanduser(app_dir) if app_dir else '(sin APP_DIR: usá --inspeccionar)'}")
        cuentas = [c for c in runner.CUENTAS
                   if os.environ.get("DEMO_EMAIL" if c == "organizador" else f"DEMO_{c.upper()}_EMAIL")]
        print(f"Cuentas: {', '.join(cuentas) or '(ninguna en .env)'}  (CUENTA en cada escena)")
        print(f"Escenas: {cfg['_SCENES_DIR']}")
        if not available:
            print("  (ninguna todavía: copiá escenas/_plantilla.py)")
        for name, path in available.items():
            mod = runner.load_module(path, f"escena_{name}")
            print(f"  {name:24s} {getattr(mod, 'TITLE', '')}")
        return

    scenes = a.escenas or list(available)
    missing = [s for s in scenes if s not in available]
    if missing:
        sys.exit(f"ERROR: no existe la escena {', '.join(missing)}. Usá --listar.")
    if not scenes:
        sys.exit(f"No hay escenas en {cfg['_SCENES_DIR']}. Copiá escenas/_plantilla.py.")

    if a.hoja:
        for name in scenes:
            out_dir = cfg["_OUTPUT_DIR"] / name
            for prof in profiles:
                res = post.contact_sheet(out_dir, name, prof)
                if not res:
                    print(f"● {name} [{prof}]: sin video todavía (grabalo primero)")
                    continue
                sheet, every = res
                print(f"● {name} [{prof}] un cuadro cada {every:.1f} s")
                print(f"  Hoja:       {sheet.relative_to(ROOT)}")
                print(f"  Subtítulos: {(out_dir / f'{name}-{prof}.srt').relative_to(ROOT)}")
        return

    music = False if a.sin_musica else a.musica
    asyncio.run(runner.run(cfg, scenes, profiles, headed=a.ver, remix_only=a.remezclar,
                           music_override=music, webm=a.webm, voice_override=a.voz))


if __name__ == "__main__":
    main()
