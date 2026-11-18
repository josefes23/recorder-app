"""Puerto `PosterStore`: las portadas en pequeño de la biblioteca, una por video, en una carpeta."""

from __future__ import annotations

import os
from pathlib import Path

from app.infrastructure.files import unlink


class FilePosterStore:
    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def read(self, video_id: int) -> bytes | None:
        path = self._path(video_id)
        return path.read_bytes() if path.is_file() else None

    def save(self, video_id: int, data: bytes) -> None:
        target = self._path(video_id)
        self._dir.mkdir(parents=True, exist_ok=True)
        # Escribir aparte y renombrar: dos peticiones a la vez nunca leen media imagen.
        partial = target.with_name(f".{target.name}.{os.getpid()}.part")
        partial.write_bytes(data)
        os.replace(partial, target)

    def remove(self, video_id: int) -> None:
        path = self._path(video_id)
        if path.is_file():
            unlink(path)

    def _path(self, video_id: int) -> Path:
        # Un entero, no un nombre: no hay forma de salirse de la carpeta.
        return self._dir / f"{int(video_id)}.jpg"
