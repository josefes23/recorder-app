"""Puerto `MusicStore`: la galería de música como carpeta de `data/`."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.application.ports import Readable
from app.domain.music import Track, is_music
from app.infrastructure import ffmpeg
from app.infrastructure.files import unlink


class FileMusicStore:
    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def list(self) -> list[Track]:
        if not self._dir.is_dir():
            return []
        return [
            Track(p.name, ffmpeg.probe_duration(p) or 0.0, p.stat().st_size / 1e6)
            for p in sorted(self._dir.iterdir(), key=lambda p: p.name.lower())
            if p.is_file() and is_music(p.name)
        ]

    def path(self, name: str) -> Path | None:
        path = self._dir / Path(name).name
        return path if path.is_file() and is_music(path.name) else None

    def save(self, name: str, stream: Readable) -> str:
        self._dir.mkdir(parents=True, exist_ok=True)
        target = self._dir / Path(name).name
        # Aparte y renombrada al final, como los fondos: una subida cortada no
        # deja una pista a medias que parezca buena.
        partial = target.with_name(target.name + ".part")
        try:
            with partial.open("wb") as fh:
                shutil.copyfileobj(stream, fh)
            partial.replace(target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        return target.name

    def remove(self, name: str) -> None:
        path = self.path(name)
        if path:
            unlink(path)
