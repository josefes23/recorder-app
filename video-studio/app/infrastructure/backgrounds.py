"""La galería de fondos como carpeta del generador."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.application.ports import Readable
from app.domain.background import Background, is_supported
from app.infrastructure import ffmpeg


class FileBackgroundStore:
    def __init__(self, directory: Path, thumbs_dir: Path) -> None:
        self._dir = directory
        self._thumbs = thumbs_dir

    def list(self) -> list[Background]:
        if not self._dir.is_dir():
            return []
        items = []
        for path in sorted(self._dir.iterdir()):
            if not path.is_file() or not is_supported(path.name):
                continue
            thumb = ffmpeg.thumbnail(path, self._thumbs)
            items.append(Background.describe(
                name=path.name,
                duration=ffmpeg.probe_duration(path),
                size_bytes=path.stat().st_size,
                thumb=thumb.name if thumb else None,
            ))
        return items

    def has(self, name: str) -> bool:
        return self.path(name) is not None

    def path(self, name: str) -> Path | None:
        """El archivo del fondo, solo si está en la galería y es de un tipo admitido."""
        path = self._dir / Path(name).name
        return path if path.is_file() and is_supported(path.name) else None

    def read(self, name: str) -> bytes | None:
        path = self.path(name)
        return path.read_bytes() if path else None

    def save(self, name: str, stream: Readable) -> str:
        target = self._dir / Path(name).name
        target.parent.mkdir(parents=True, exist_ok=True)
        # Se escribe aparte y se renombra al final: si la copia se corta, la
        # galería no se queda con un archivo a medias que parezca válido.
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
        if path is None:
            return
        # La miniatura va ligada al archivo: sin él solo ocupa sitio.
        ffmpeg.thumbnail_file(path, self._thumbs).unlink(missing_ok=True)
        path.unlink()

    def thumbnail_path(self, thumb: str) -> Path | None:
        path = self._thumbs / Path(thumb).name
        return path if path.is_file() else None
