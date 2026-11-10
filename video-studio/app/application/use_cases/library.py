"""La biblioteca de videos ya renderizados."""

from __future__ import annotations

from pathlib import Path

from app.application.ports import VideoFiles, VideoRepository
from app.domain.errors import NotFoundError
from app.domain.video import Video


class LibraryUseCases:
    def __init__(self, videos: VideoRepository, files: VideoFiles) -> None:
        self._videos = videos
        self._files = files

    def list(self) -> list[Video]:
        return self._videos.list()

    def file_of(self, video_id: int) -> Path:
        record = self._videos.get(video_id)
        if record is None or not record.filename:
            raise NotFoundError("Ese video todavía no tiene archivo.")
        path = Path(record.filename)
        if not self._files.exists(path):
            raise NotFoundError("El archivo ya no está en el disco.")
        return path

    def delete(self, video_id: int) -> None:
        """Borra la ficha y el archivo: la biblioteca no deja huérfanos en disco."""
        record = self._videos.get(video_id)
        if record is None:
            raise NotFoundError("No existe ese video.")
        if record.filename:
            self._files.remove(Path(record.filename))
        self._videos.remove(video_id)
