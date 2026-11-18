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
import shutil
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.domain.background import VIDEO_EXTS  # noqa: E402
from app.domain.captions import clip_to_duration  # noqa: E402
from app.domain.dialogue import NARRATOR, Line, split_dialogue, spoken_text, validate_voices  # noqa: E402
from app.domain.music import validate_volume  # noqa: E402
from app.domain.production import format_by_id  # noqa: E402
from app.domain.motion import scene_seed  # noqa: E402
from app.domain.scene import Scene, synced_to_voice, timeline_spans  # noqa: E402
from app.domain.script import clean_script  # noqa: E402
from app.domain.style import CaptionStyle  # noqa: E402
from app.domain.transition import Transition, plan_changes, reach, read_transition  # noqa: E402
from app.domain.video import RenderSpec  # noqa: E402
from app.domain.voice_take import take_key, take_request  # noqa: E402
from app.infrastructure.generator import apply_format, apply_style, load_generator  # noqa: E402
from app.infrastructure.motion import moving_image  # noqa: E402
from app.infrastructure.paths import Paths  # noqa: E402
from app.infrastructure.soundtrack import ambient_sound, music_bed, soundtrack  # noqa: E402
from app.infrastructure.takes import FileTakeStore  # noqa: E402
from app.infrastructure.transitions import chain  # noqa: E402
from app.infrastructure.voice import EngineVoiceSynthesizer  # noqa: E402


def emit(**payload) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def build_track(gen, backgrounds_dir: Path, scenes: list[dict], topic: str, duration: float,
                default: Transition | None = None):
    """
    Encadena los fondos de la línea de tiempo en una sola pista.

    Las imágenes fijas llevan el movimiento del estudio (`domain.motion`):
    zoom continuo y un cambio de encuadre cada 3 o 4 segundos. Los clips de
    video ya se mueven solos y van tal cual, como el fondo generado del motor.

    Cada escena entra con su transición, o con `default` si no eligió ninguna
    (`domain.transition`), y la usa también para sus cambios de encuadre. La
    transición se centra en el corte, así que cada fondo se pinta desde la
    mitad de la transición con que entra hasta la mitad de la siguiente.
    """
    from moviepy import CompositeVideoClip

    spans = timeline_spans((Scene.from_dict(s) for s in scenes), duration)
    if not spans:
        return gen.build_background(None, topic, duration)

    entries = [span.transition or default or Transition() for span in spans]
    bounds = [span.start for span in spans] + [spans[-1].end]
    changes = plan_changes(bounds, entries[1:])

    pieces = []
    for index, (span, (start, end), entry) in enumerate(zip(spans, reach(bounds, changes), entries)):
        path = backgrounds_dir / span.background
        length = end - start
        emit(phase="background", progress=0.25,
             message=f"{span.start:.1f}-{span.end:.1f}s · {span.background}")
        if path.is_file() and path.suffix.lower() in gen.IMAGE_EXTS:
            # Sale ya a la medida exacta del cuadro, así que se ahorra el
            # CompositeVideoClip de abajo: solo iguala tamaños y cuesta unos
            # 115 ms por fotograma, el doble que pintar el fotograma.
            size = (gen.WIDTH, gen.HEIGHT)
            pieces.append((start, moving_image(path, length, size, scene_seed(index, span.background), entry)))
            continue
        clip = gen.build_background(path if path.is_file() else None, topic, length)
        # Normaliza el lienzo: las transiciones mezclan fotogramas del mismo tamaño.
        pieces.append((start, CompositeVideoClip([clip], size=(gen.WIDTH, gen.HEIGHT)).with_duration(length)))

    return chain(pieces, changes, bounds[-1])


def sound_layers(job: RenderSpec, paths: Paths, scenes: list[dict], words: list[dict], duration: float) -> list:
    """Lo que suena debajo de la voz: la música elegida y el sonido de los clips."""
    layers = []
    if job.music:
        track = paths.music / Path(job.music).name
        if track.is_file():
            emit(phase="render", progress=0.28, message=f"Música: {track.name}")
            layers.append(music_bed(track, duration, words, validate_volume(job.music_volume)))
        else:
            emit(phase="render", progress=0.28, message=f"«{job.music}» ya no está en la galería de música: va sin música")
    if job.ambient:
        spans = timeline_spans((Scene.from_dict(s) for s in scenes), duration)
        clips = [
            (paths.backgrounds / span.background, span.start, span.duration)
            for span in spans
            if (paths.backgrounds / span.background).suffix.lower() in VIDEO_EXTS
            and (paths.backgrounds / span.background).is_file()
        ]
        layers += ambient_sound(clips)
    return layers


def main() -> None:
    paths = Paths.default()
    gen = load_generator(paths.generator)

    job = RenderSpec.from_dict(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
    style = CaptionStyle.from_dict(job.style)
    apply_style(gen, style)
    apply_format(gen, format_by_id(job.format))

    script = clean_script(job.script)
    if not script:
        emit(error="El guion está vacío.")
        sys.exit(1)

    out_path = Path(job.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_mp3 = out_path.with_suffix(".voz.mp3")

    # Con voces asignadas, el guion es un diálogo: cada intervención con la voz
    # de su personaje. Sin ellas, una sola voz, como siempre.
    voices = validate_voices(job.voices)
    lines = split_dialogue(job.script, voices.keys()) if voices else [Line(NARRATOR, script)]
    if voices:
        script = spoken_text(lines)  # sin etiquetas: es lo que se oye y se subtitula

    # La voz es una toma (`domain.voice_take`): si ya se generó en el estudio
    # para escuchar la animática, se usa esa —mismos tiempos que se vieron—; si
    # no, se genera aquí y se guarda con la misma clave, para que el video
    # recuerde en qué segundo dijo cada palabra.
    request = take_request(job.script, job.voice, job.rate, job.pitch, voices)
    key = take_key(request)
    takes = FileTakeStore(Path(job.takes_dir) if job.takes_dir else paths.takes)
    take, saved_audio = takes.get(key), takes.audio(key)
    if take is not None and saved_audio is not None:
        emit(phase="tts", progress=0.05, message="Voz ya generada: se usa la que escuchaste")
        shutil.copyfile(saved_audio, tmp_mp3)
        words = take.words
    else:
        emit(phase="tts", progress=0.05, message="Generando voz…" if not voices else f"Generando {len(lines)} intervenciones…")
        audio_bytes, words, seconds = EngineVoiceSynthesizer(gen, out_path.parent).synthesize(request)
        tmp_mp3.write_bytes(audio_bytes)
        takes.save(key, audio_bytes, words, seconds)

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

    # Las escenas llegan en segundos estimados; con la voz ya hecha, cada una
    # entra cuando la voz dice su texto.
    # Contra el guion tal cual, etiquetas «ANA:» incluidas: con él se estimaron
    # los segundos de cada escena. La voz no dice las etiquetas y el alineador
    # las salta, así que los cortes caen donde deben.
    scenes = [
        s.as_dict() for s in synced_to_voice(map(Scene.from_dict, job.scenes), clean_script(job.script), words or [])
    ]
    background = build_track(gen, paths.backgrounds, scenes, job.topic, duration, read_transition(job.transition))

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
        .with_audio(soundtrack(audio, sound_layers(job, paths, scenes, words or [], duration)))
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
