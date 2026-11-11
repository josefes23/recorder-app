#!/usr/bin/env python3
"""
Ejecuta un render completo en un proceso aparte y emite progreso por stdout.

Uso:  python -m app.infrastructure.render_worker <ruta-al-job.json>

Solo importa el dominio y el puente al motor: ni FastAPI ni SQLite. Lo que el
servidor necesita saber viaja como líneas JSON por stdout.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.domain.captions import clip_to_duration  # noqa: E402
from app.domain.motion import scene_seed  # noqa: E402
from app.domain.scene import Scene, timeline_spans  # noqa: E402
from app.domain.script import clean_script  # noqa: E402
from app.domain.style import CaptionStyle  # noqa: E402
from app.domain.video import RenderSpec  # noqa: E402
from app.domain.voice import DEFAULT_PITCH, DEFAULT_RATE, DEFAULT_VOICE  # noqa: E402
from app.infrastructure.generator import apply_style, load_generator  # noqa: E402
from app.infrastructure.motion import moving_image  # noqa: E402
from app.infrastructure.paths import Paths  # noqa: E402


def emit(**payload) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def build_track(gen, backgrounds_dir: Path, scenes: list[dict], topic: str, duration: float):
    """
    Encadena los fondos de la línea de tiempo en una sola pista.

    Las imágenes fijas llevan el movimiento del estudio (`domain.motion`):
    zoom continuo y un corte de encuadre cada 3 o 4 segundos. Los clips de
    video ya se mueven solos y van tal cual, como el fondo generado del motor.
    """
    from moviepy import CompositeVideoClip, concatenate_videoclips

    spans = timeline_spans((Scene.from_dict(s) for s in scenes), duration)
    if not spans:
        return gen.build_background(None, topic, duration)

    clips = []
    for index, span in enumerate(spans):
        path = backgrounds_dir / span.background
        emit(phase="background", progress=0.25,
             message=f"{span.start:.1f}-{span.end:.1f}s · {span.background}")
        if path.is_file() and path.suffix.lower() in gen.IMAGE_EXTS:
            # Sale ya a la medida exacta del cuadro, así que se ahorra el
            # CompositeVideoClip de abajo: solo iguala tamaños y cuesta unos
            # 115 ms por fotograma, el doble que pintar el fotograma.
            size = (gen.WIDTH, gen.HEIGHT)
            clips.append(moving_image(path, span.duration, size, scene_seed(index, span.background)))
            continue
        clip = gen.build_background(path if path.is_file() else None, topic, span.duration)
        # Normaliza el lienzo: concatenate_videoclips exige tamaños idénticos.
        clips.append(
            CompositeVideoClip([clip], size=(gen.WIDTH, gen.HEIGHT)).with_duration(span.duration)
        )

    return concatenate_videoclips(clips) if clips else gen.build_background(None, topic, duration)


def main() -> None:
    paths = Paths.default()
    gen = load_generator(paths.generator)

    job = RenderSpec.from_dict(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
    style = CaptionStyle.from_dict(job.style)
    apply_style(gen, style)

    script = clean_script(job.script)
    if not script:
        emit(error="El guion está vacío.")
        sys.exit(1)

    out_path = Path(job.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_mp3 = out_path.with_suffix(".voz.mp3")

    emit(phase="tts", progress=0.05, message="Generando voz…")
    words = gen.synthesize_voice(
        script, job.voice or DEFAULT_VOICE, job.rate or DEFAULT_RATE, job.pitch or DEFAULT_PITCH, tmp_mp3,
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
    captions = clip_to_duration(captions, duration)
    emit(phase="captions", progress=0.25, message=f"{len(captions)} bloques")

    background = build_track(gen, paths.backgrounds, job.scenes, job.topic, duration)

    emit(phase="render", progress=0.30, message="Renderizando…")

    from moviepy import CompositeVideoClip
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

    # Se reimplanta el ensamblado final en vez de llamar a gen.render(): esa
    # función no acepta un logger, y sin él no habría barra de progreso. La
    # parte con lógica real (build_caption_clips) se reutiliza tal cual.
    caption_clips = gen.build_caption_clips(captions, gen.resolve_font(None), style.animate)
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

    if not job.keep_audio:
        tmp_mp3.unlink(missing_ok=True)

    emit(done=True, output=str(out_path), duration=round(duration, 1),
         size_mb=round(out_path.stat().st_size / 1e6, 1), captions=len(captions))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - el error debe llegar a la interfaz
        emit(error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc()[-1500:])
        sys.exit(1)
