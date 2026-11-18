"""Puerto `TakeStore`: las tomas de voz en una carpeta, `<clave>.json` y `<clave>.mp3`."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.domain.voice_take import VoiceTake, clean_words, is_take_key
from app.infrastructure.files import unlink

#: Audios que se guardan. Cada minuto de voz ocupa un mega, y escuchar después
#: de cada cambio del guion genera uno nuevo; las marcas no se borran nunca.
MAX_AUDIO = 40


class FileTakeStore:
    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def get(self, key: str) -> VoiceTake | None:
        if not is_take_key(key):
            return None
        marks = self._dir / f"{key}.json"
        if not marks.is_file():
            return None
        try:
            data = json.loads(marks.read_text(encoding="utf-8"))
            duration = float(data["duration"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        return VoiceTake(key, duration, clean_words(data.get("words")), audio=(self._dir / f"{key}.mp3").is_file())

    def audio(self, key: str) -> Path | None:
        if not is_take_key(key):
            return None
        path = self._dir / f"{key}.mp3"
        return path if path.is_file() else None

    def save(self, key: str, audio: bytes, words: list[dict], duration: float) -> VoiceTake:
        if not is_take_key(key):
            raise ValueError(f"Clave de toma no válida: {key!r}")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._write(self._dir / f"{key}.mp3", audio)
        marks = {"duration": duration, "words": clean_words(words)}
        self._write(self._dir / f"{key}.json", json.dumps(marks, ensure_ascii=False).encode("utf-8"))
        self._prune()
        return VoiceTake(key, duration, marks["words"], audio=True)

    def _write(self, target: Path, data: bytes) -> None:
        # Aparte y renombrado: el render y la interfaz pueden pedir la misma toma a la vez.
        partial = target.with_name(f".{target.name}.{os.getpid()}.part")
        partial.write_bytes(data)
        os.replace(partial, target)

    def _prune(self) -> None:
        audios = sorted(self._dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in audios[MAX_AUDIO:]:
            unlink(old)
