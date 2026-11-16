"""Puerto `ReferenceStore`: las imágenes de referencia de la biblioteca, en una carpeta."""

from __future__ import annotations

import os
from pathlib import Path

from app.domain.saved_characters import is_reference_name
from app.infrastructure.files import unlink


class FileReferenceStore:
    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def save(self, name: str, data: bytes) -> str:
        target = self._target(name)
        self._dir.mkdir(parents=True, exist_ok=True)
        # Escribir aparte y renombrar: quien lea a la vez ve la imagen vieja o
        # la nueva, nunca media.
        partial = target.with_name(f".{target.name}.part")
        partial.write_bytes(data)
        os.replace(partial, target)
        return name

    def read(self, name: str) -> bytes | None:
        path = self.path(name)
        return path.read_bytes() if path else None

    def path(self, name: str) -> Path | None:
        if not is_reference_name(name):
            return None
        target = self._dir / name
        return target if target.is_file() else None

    def remove(self, name: str) -> None:
        path = self.path(name)
        if path:
            unlink(path)

    def _target(self, name: str) -> Path:
        if not is_reference_name(name):
            raise ValueError(f"Nombre de referencia no válido: {name!r}")
        return self._dir / name
