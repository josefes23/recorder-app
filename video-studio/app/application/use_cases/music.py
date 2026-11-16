"""La galería de música: subir, listar, escuchar y borrar pistas."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from app.application.ports import MusicStore
from app.domain.errors import NotFoundError
from app.domain.music import Track, track_name


class MusicUseCases:
    def __init__(self, store: MusicStore) -> None:
        self._store = store

    def list(self) -> list[Track]:
        return self._store.list()

    def upload(self, filename: str | None, stream: BinaryIO) -> tuple[str, list[Track]]:
        name = self._store.save(track_name(filename), stream)
        return name, self._store.list()

    def file(self, name: str) -> Path:
        path = self._store.path(name)
        if path is None:
            raise NotFoundError(f"«{name}» no está en la galería de música.")
        return path

    def delete(self, name: str) -> list[Track]:
        self.file(name)
        self._store.remove(name)
        return self._store.list()
