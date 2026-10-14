#!/usr/bin/env python3
"""
Ejecuta un render completo en un proceso aparte y emite progreso por stdout.

Va en su propio proceso por dos razones: un render de varios minutos bloquearía
el servidor web, y así el progreso se puede leer línea a línea desde la cola.

Uso:  python -m app.render_worker <ruta-al-job.json>
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import engine
from app.engine import gen


def emit(**payload) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def build_track(scenes: list[dict], topic: str, duration: float):
    """Encadena los fondos de la línea de tiempo en una sola pista."""
    from moviepy import CompositeVideoClip, concatenate_videoclips

    usable = [s for s in (scenes or []) if s.get("background")]
    if not usable:
        return gen.build_background(None, topic, duration)

    ordered = sorted(usable, key=lambda s: float(s.get("start", 0)))
    ordered[0]["start"] = 0.0

    clips = []
    for i, scene in enumerate(ordered):
        start = float(scene["start"])
        end = float(ordered[i + 1]["start"]) if i + 1 < len(ordered) else duration
        span = min(end, duration) - start
        if span <= 0.05:
            continue
        path = engine.background_dir() / scene["background"]
        emit(phase="background", progress=0.25,
             message=f"{start:.1f}-{start + span:.1f}s · {scene['background']}")
        clip = gen.build_background(path if path.is_file() else None, topic, span)
        # Normaliza el lienzo: concatenate_videoclips exige tamaños idénticos.
        clips.append(
            CompositeVideoClip([clip], size=(gen.WIDTH, gen.HEIGHT)).with_duration(span)
        )

    return concatenate_videoclips(clips) if clips else gen.build_background(None, topic, duration)


def main() -> None:
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    engine.apply_style(job.get("style") or {})

    script = engine.clean_script(job["script"])
    if not script:
        emit(error="El guion está vacío.")
        sys.exit(1)

    out_path = Path(job["output"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_mp3 = out_path.with_suffix(".voz.mp3")

    emit(phase="tts", progress=0.05, message="Generando voz…")
    words = gen.synthesize_voice(
        script, job.get("voice", "es-MX-DaliaNeural"),
        job.get("rate", "+8%"), job.get("pitch", "+0Hz"), tmp_mp3,
    )

    from moviepy import AudioFileClip
    with AudioFileClip(str(tmp_mp3)) as audio:
        duration = float(audio.duration)
    emit(phase="tts", progress=0.15, message=f"Audio de {duration:.1f}s", duration=duration)

    emit(phase="captions", progress=0.20, message="Sincronizando subtítulos…")
    if words:
        captions = gen.group_captions(gen.attach_punctuation(words, script))
    else:
        captions = gen.captions_from_text(script, duration)
    captions = [c for c in captions if c["start"] < duration]
    if captions:
        last = captions[-1]
        last["duration"] = min(last["duration"], duration - last["start"])
    emit(phase="captions", progress=0.25, message=f"{len(captions)} bloques")

    background = build_track(job.get("scenes") or [], job.get("topic", ""), duration)

    emit(phase="render", progress=0.30, message="Renderizando…")

    from proglog import ProgressBarLogger

    class Reporter(ProgressBarLogger):
        """Traduce la barra de moviepy a líneas JSON de progreso."""

        def bars_callback(self, bar, attr, value, old_value=None):
            if attr != "index":
                return
            total = self.bars[bar].get("total") or 0
            if total:
                emit(phase="render", progress=0.30 + 0.68 * (value / total),
                     message=f"Fotograma {value} de {total}")

    # Reimplantamos el ensamblado final en vez de llamar a gen.render(): esa
    # función no acepta un logger, y sin él no habría barra de progreso.
    # La parte con lógica real (build_caption_clips) se reutiliza tal cual.
    import os

    from moviepy import CompositeVideoClip

    animate = bool((job.get("style") or {}).get("animate", True))
    caption_clips = gen.build_caption_clips(captions, gen.resolve_font(None), animate)
    audio = AudioFileClip(str(tmp_mp3))
    video = (
        CompositeVideoClip([background, *caption_clips], size=(gen.WIDTH, gen.HEIGHT))
        .with_duration(duration)
        .with_audio(audio)
    )
    video.write_videofile(
        str(out_path), fps=gen.FPS, codec="libx264", audio_codec="aac",
        preset="medium", threads=os.cpu_count() or 4,
        temp_audiofile=str(out_path.with_suffix(".temp-audio.m4a")),
        logger=Reporter(),
    )
    video.close()
    audio.close()

    if not job.get("keep_audio"):
        tmp_mp3.unlink(missing_ok=True)

    emit(done=True, output=str(out_path), duration=round(duration, 1),
         size_mb=round(out_path.stat().st_size / 1e6, 1), captions=len(captions))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - el error debe llegar a la interfaz
        emit(error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc()[-1500:])
        sys.exit(1)
