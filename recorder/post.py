"""
Postproducción con ffmpeg: recorte, voz, música con ducking, subtítulos,
póster y fragmento HTML para la landing.

Todo sale de la carpeta de trabajo (.work/<perfil>/raw.mp4 + timeline.json),
así que se puede rehacer (otra música, otro estilo de subtítulos) sin volver a
grabar: `python grabar.py --remezclar`.
"""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

from . import animar, ff, subtitles

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "fonts"
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"}


def pick_music(music_cfg: dict) -> Path | None:
    f = music_cfg.get("file")
    if not f:
        return None
    if f == "auto":
        folder = ROOT / music_cfg.get("folder", "musica")
        tracks = sorted(p for p in folder.glob("*") if p.suffix.lower() in AUDIO_EXTS)
        return random.choice(tracks) if tracks else None
    p = Path(f)
    p = p if p.is_absolute() else (ROOT / p)
    if not p.is_file():
        raise SystemExit(f"ERROR: no existe la música {p}")
    return p


def duck_filter(timeline: list[dict], level: float, attack: float = 0.3,
                release: float = 0.6) -> str:
    """volume=... con rampas suaves: 1.0 sin voz, `level` durante cada frase."""
    ramps = []
    for it in timeline:
        s, e = it["start"], it["start"] + it["duration"]
        ramps.append(f"clip((t-{s - attack:.3f})/{attack},0,1)*clip(({e + release:.3f}-t)/{release},0,1)")
    expr = ramps[0]
    for r in ramps[1:]:
        expr = f"max({expr},{r})"
    return f"volume='1-{1 - level:.3f}*{expr}':eval=frame"


def render(work: Path, out_dir: Path, name: str, cfg: dict, music: Path | None,
           webm: bool = False, title: str = "") -> dict:
    data = json.loads((work / "timeline.json").read_text(encoding="utf-8"))
    raw = work / "raw.mp4"
    trim = data["trim_start"]
    dur = round(ff.duration(raw) - trim, 3)
    width, height = ff.size(raw)
    timeline = data["timeline"]
    profile = data["profile"]
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------- animaciones: zoom, transiciones, intro y cierre --------- #
    anim, _ = animar.ajustes(cfg)
    video_in, v_trim, total = raw, trim, dur
    if animar.activo(anim):
        comp = animar.componer(raw, trim, dur, work / "animado.mp4", data, cfg, title or name)
        video_in, v_trim, total = work / "animado.mp4", 0.0, comp["total"]
        # La intro corre todo lo que suena y se lee.
        timeline = [{**it, "start": round(it["start"] + comp["intro"], 3)} for it in timeline]
        dur_main = comp["intro"] + dur
    else:
        dur_main = dur

    # ---------- subtítulos + transcripción ------------------------------ #
    sub_cfg = cfg["SUBTITLES"]
    per = sub_cfg.get(profile) or sub_cfg.get("mobile" if height > width else "desktop", {})
    caps = subtitles.build(timeline, dur_main, per.get("max_chars", 42), per.get("max_words", 8))
    # Quemados: resaltando la palabra que se dice. Los .vtt/.srt, por bloque.
    burn_items = subtitles.estados(caps) if anim.get("subtitulos_palabra") else caps
    base = out_dir / f"{name}-{profile}"
    subtitles.write_srt(caps, base.with_suffix(".srt"))
    subtitles.write_vtt(caps, base.with_suffix(".vtt"))
    subtitles.write_txt(timeline, out_dir / f"{name}-transcripcion.txt")
    ass = work / "subs.ass"
    style = {**sub_cfg.get("style", {}), **per}
    band = subtitles.band_height(width, height, style) if style.get("placement") == "band" else 0
    subtitles.write_ass(burn_items, ass, width, height + band, style)
    dur = total

    # ---------- audio: voz + música con ducking ------------------------- #
    mcfg = cfg["MUSIC"]
    inputs = ["-ss", f"{v_trim:.3f}", "-i", str(video_in)]
    filters, voice_labels = [], []
    for i, item in enumerate(timeline):
        inputs += ["-i", item["audio"]]
        d = max(0, int(round(item["start"] * 1000)))
        filters.append(f"[{i + 1}:a]aresample=48000,aformat=channel_layouts=stereo,"
                       f"adelay={d}|{d}[v{i}]")
        voice_labels.append(f"[v{i}]")
    n = len(voice_labels)
    if n:
        filters.append(f"{''.join(voice_labels)}amix=inputs={n}:normalize=0:duration=longest,"
                       f"volume={mcfg.get('voice_volume', 1.0)},apad[voice]")

    audio_out = None
    if music:
        mi = n + 1
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        fade = min(2.0, dur / 4)
        filters.append(
            f"[{mi}:a]aresample=48000,aformat=channel_layouts=stereo,"
            f"volume={mcfg.get('volume', 0.2)},atrim=0:{dur},"
            f"afade=t=in:d=1,afade=t=out:st={max(0, dur - fade):.2f}:d={fade:.2f}[mus]")
        if n and mcfg.get("duck", True):
            # La música baja mientras habla la voz. En vez de un compresor
            # (reacciona tarde y apenas baja 3 dB) se usa automatización exacta:
            # sabemos cuándo empieza y termina cada frase.
            filters.append(f"[mus]{duck_filter(timeline, mcfg.get('duck_level', 0.35))}[duck]")
            filters.append("[duck][voice]amix=inputs=2:normalize=0:duration=first[amix]")
        elif n:
            filters.append("[mus][voice]amix=inputs=2:normalize=0:duration=first[amix]")
        else:
            filters.append("[mus]anull[amix]")
        audio_out = "amix"
    elif n:
        filters.append("[voice]anull[amix]")
        audio_out = "amix"
    if audio_out:
        filters.append("[amix]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]")

    video_f = "fps=30,format=yuv420p"
    common_v = ["-c:v", "libx264", "-preset", "slow", "-crf", str(cfg.get("CRF", 22)),
                "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    audio_args = (["-map", "[aout]", "-c:a", "aac", "-b:a", "160k"] if audio_out else ["-an"])

    clean = base.with_suffix(".mp4")
    rec = data.get("grabacion", {})
    tag = f"app-demo-recorder {rec.get('commit', '?')} {rec.get('fecha', '')}".strip()
    args = [*inputs, "-filter_complex", ";".join(filters + [f"[0:v]{video_f}[vout]"]),
            "-map", "[vout]", *audio_args, *common_v, "-metadata", f"comment={tag}",
            "-t", f"{dur}", str(clean)]
    ff.run(args)
    outputs = {"video": clean}

    # ---------- versión con subtítulos quemados ------------------------- #
    if sub_cfg.get("burn", True) and caps:
        burned = out_dir / f"{name}-{profile}-subs.mp4"
        pad = (f"pad=iw:ih+{band}:0:0:color={style.get('band_color', '#111111').replace('#', '0x')}"
               if band else "")
        if ff.has_filter("ass"):
            # cwd = carpeta de trabajo: evita escapar rutas con ':' o espacios.
            vf = "ass=subs.ass"
            if FONTS.is_dir():
                # La fuente viaja con el repo: los subtítulos salen iguales en
                # los tres sistemas, tengan o no instalada la fuente.
                shutil.copytree(FONTS, work / "fonts", dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("*.md", "*.txt"))
                vf += ":fontsdir=fonts"
            if pad:
                vf = f"{pad},{vf}"
            ff.run(["-i", str(clean.resolve()), "-vf", vf, "-c:a", "copy",
                    *common_v, str(burned.resolve())], cwd=work)
        else:
            # Sin libass (el ffmpeg de Homebrew; en Mac Intel no hay ffmpeg-full):
            # cada bloque se dibuja como imagen con la fuente de fonts/ y se
            # superpone con overlay, que tiene cualquier ffmpeg.
            shutil.rmtree(work / "subs", ignore_errors=True)   # de una mezcla anterior
            imgs = subtitles.write_images(burn_items, work / "subs", width, height, band, style,
                                          FONTS)
            inputs, chain, last = ["-i", str(clean.resolve())], [], "0:v"
            if pad:
                chain.append(f"[0:v]{pad}[p]")
                last = "p"
            for i, im in enumerate(imgs, 1):
                inputs += ["-i", im["png"].relative_to(work).as_posix()]
                chain.append(f"[{last}][{i}:v]overlay={im['x']}:{im['y']}:"
                             f"enable='between(t,{im['start']:.3f},{im['end']:.3f})'[s{i}]")
                last = f"s{i}"
            ff.run([*inputs, "-filter_complex", ";".join(chain), "-map", f"[{last}]",
                    "-map", "0:a?", "-c:a", "copy", *common_v, str(burned.resolve())], cwd=work)
        outputs["video_subs"] = burned

    # ---------- webm opcional, póster ----------------------------------- #
    if webm:
        w = base.with_suffix(".webm")
        ff.run(["-i", str(clean), "-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "0",
                "-row-mt", "1", "-deadline", "good", "-cpu-used", "4",
                *(["-c:a", "libopus", "-b:a", "96k"] if audio_out else ["-an"]), str(w)])
        outputs["webm"] = w
    poster = base.with_suffix(".jpg")
    ff.run(["-ss", f"{min(cfg.get('POSTER_AT', 1.0), max(0, dur - 0.1)):.2f}", "-i", str(clean),
            "-frames:v", "1", "-q:v", "3", str(poster)])
    outputs.update(poster=poster, srt=base.with_suffix(".srt"), vtt=base.with_suffix(".vtt"))
    outputs["duration"] = dur
    outputs["size"] = (width, height)

    # ---------- con qué se hizo: va junto al video a la carpeta compartida #
    info = {**rec, "musica": music.name if music else None,
            "subtitulos_quemados": "video_subs" in outputs, "duracion": dur}
    base.with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    outputs["info"] = base.with_suffix(".json")
    return outputs


def contact_sheet(out_dir: Path, name: str, profile: str) -> tuple[Path, float] | None:
    """Hoja de cuadros para revisar un video de un vistazo: hasta 16 cuadros
    repartidos a lo largo de todo el video. Usa la versión con subtítulos si está."""
    video = out_dir / f"{name}-{profile}-subs.mp4"
    if not video.is_file():
        video = out_dir / f"{name}-{profile}.mp4"
    if not video.is_file():
        return None
    w, h = ff.size(video)
    cols, rows, thumb = (8, 2, 240) if h > w else (4, 4, 480)
    every = max(1.0, ff.duration(video) / 15)
    sheet = out_dir / ".work" / f"hoja-{profile}.png"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    ff.run(["-i", str(video), "-vf", f"fps=1/{every:.3f},scale={thumb}:-1,tile={cols}x{rows}",
            "-frames:v", "1", str(sheet)])
    return sheet, every


def write_snippet(out_dir: Path, name: str, title: str, profiles: list[str]) -> Path:
    """HTML listo para pegar en la landing: celular en pantallas chicas, escritorio en grandes."""
    # Un <video> por perfil (no <source media>): cada grabación tiene sus
    # propios tiempos, así que cada una necesita su propio .vtt.
    found = [p for p in profiles if (out_dir / f"{name}-{p}.mp4").is_file()]
    blocks = []
    for p in found:
        cls = f"demo-{p}" if len(found) > 1 else "demo-video"
        blocks.append(
            f'<video class="{cls}" controls playsinline preload="metadata" poster="{name}-{p}.jpg">\n'
            f'  <source src="{name}-{p}.mp4" type="video/mp4">\n'
            f'  <track kind="subtitles" srclang="es" label="Español" src="{name}-{p}.vtt">\n'
            f'</video>')
    css = "video{width:100%;height:auto;border-radius:16px}"
    if len(found) > 1:
        css += ("\n  .demo-mobile{display:none;max-width:420px;margin:auto}"
                "\n  @media (max-width:767px){.demo-desktop{display:none}.demo-mobile{display:block}}")
    html = f"""<!-- {title} — generado por app-demo-recorder.
     Se ve la versión de celular en pantallas chicas y la de escritorio en grandes.
     Para un loop mudo y automático (hero): usá los *-subs.mp4 (subtítulos
     quemados) con los atributos  autoplay muted loop playsinline  y sin controls. -->
<style>
  {css}
</style>
{chr(10).join(blocks)}
"""
    path = out_dir / "landing.html"
    path.write_text(html, encoding="utf-8")
    return path
