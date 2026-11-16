"""
La banda sonora del render: voces del diálogo, música y sonido ambiente.

Solo lo usa el worker de render. Las reglas (quién dice qué, cuánto baja la
música) están en `domain.dialogue` y `domain.music`; aquí se hacen sonar con
moviepy y el motor.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from app.domain.dialogue import NARRATOR, TURN_GAP, Line
from app.domain.music import AMBIENT_VOLUME, FADE_SECONDS, duck_envelope, voiced_intervals


def synthesize_dialogue(
    gen,
    lines: Sequence[Line],
    voices: Mapping[str, str],
    narrator: str,
    rate: str,
    pitch: str,
    out_mp3: Path,
) -> list[dict]:
    """
    Sintetiza cada intervención con la voz de su personaje y las une en
    `out_mp3`, con un silencio corto entre turnos. Devuelve las marcas de cada
    palabra ya corridas a su sitio en la pista unida, como si fuera una sola voz.
    """
    if len(lines) == 1 and lines[0].speaker == NARRATOR:
        return gen.synthesize_voice(lines[0].text, narrator, rate, pitch, out_mp3)

    from moviepy import AudioFileClip, CompositeAudioClip

    parts: list[Path] = []
    clips = []
    words: list[dict] = []
    offset = 0.0
    try:
        for i, line in enumerate(lines):
            part = out_mp3.with_name(f"{out_mp3.stem}.{i:03d}.mp3")
            parts.append(part)
            marks = gen.synthesize_voice(line.text, voices.get(line.speaker) or narrator, rate, pitch, part)
            clip = AudioFileClip(str(part))
            clips.append(clip.with_start(offset))
            words += [{**w, "start": w["start"] + offset, "end": w["end"] + offset} for w in marks]
            offset += clip.duration + TURN_GAP
        joined = CompositeAudioClip(clips)
        joined.write_audiofile(str(out_mp3), fps=44100, logger=None)
        joined.close()
    finally:
        for clip in clips:
            clip.close()
        for part in parts:
            part.unlink(missing_ok=True)
    return words


def with_gain(clip, points: Sequence[tuple[float, float]]):
    """El clip con su volumen siguiendo los puntos (segundo, ganancia), interpolados."""
    import numpy as np

    times = np.array([t for t, _ in points], dtype=float)
    gains = np.array([g for _, g in points], dtype=float)

    def scaled(get_frame, t):
        frame = get_frame(t)
        gain = np.interp(t, times, gains)
        return frame * (gain[:, None] if np.ndim(gain) else gain)

    return clip.transform(scaled, keep_duration=True)


def music_bed(path: Path, duration: float, words: Sequence[Mapping], volume: float):
    """La pista repetida hasta cubrir el video, con fundidos y bajando bajo la voz."""
    from moviepy import AudioFileClip
    from moviepy.audio.fx import AudioFadeIn, AudioFadeOut, AudioLoop

    track = AudioFileClip(str(path))
    bed = track.with_effects([AudioLoop(duration=duration)]) if track.duration < duration else track.subclipped(0, duration)
    fade = min(FADE_SECONDS, duration / 4)
    bed = bed.with_effects([AudioFadeIn(fade), AudioFadeOut(fade)])
    return with_gain(bed, duck_envelope(voiced_intervals(words), duration, volume))


def ambient_sound(spans: Sequence[tuple[Path, float, float]]):
    """
    El sonido propio de cada clip en su tramo (inicio, duración), bajo. Los
    clips sin pista de audio —casi todos los de Pexels— no aportan nada.
    """
    from moviepy import VideoFileClip

    layers = []
    for path, start, length in spans:
        source = VideoFileClip(str(path))
        if source.audio is None:
            source.close()
            continue
        audio = source.audio.subclipped(0, min(length, source.audio.duration))
        layers.append(audio.with_volume_scaled(AMBIENT_VOLUME).with_start(start))
    return layers


def soundtrack(voice, layers: Sequence):
    """La voz encima de todo lo demás. Sin capas extra, la voz tal cual."""
    if not layers:
        return voice
    from moviepy import CompositeAudioClip

    return CompositeAudioClip([*layers, voice]).with_duration(voice.duration)
