"""Estado en vivo de los renders y su reflejo en el historial."""

from __future__ import annotations

import threading

from app.application.ports import VideoRepository
from app.domain.video import ACTIVE_STATUSES, RenderResult, VideoStatus


class RenderJobs:
    """
    Implementa `RenderListener`: la cola le cuenta cómo va cada trabajo y aquí
    se decide qué ve la interfaz (progreso, fase, mensaje) y qué se persiste.
    """

    def __init__(self, videos: VideoRepository) -> None:
        self._videos = videos
        self._state: dict[int, dict] = {}
        self._lock = threading.Lock()

    # Consulta ------------------------------------------------------------- #

    def status(self, video_id: int) -> dict | None:
        """Progreso en vivo, o None si la cola no conoce ese trabajo.

        Un video renderizado antes del último arranque no está aquí: su
        estado es el del historial, y no hay nada que superponerle.
        """
        with self._lock:
            info = self._state.get(video_id)
            return dict(info) if info is not None else None

    def all_active(self) -> list[dict]:
        with self._lock:
            return [
                {"id": vid, **info}
                for vid, info in self._state.items()
                if info.get("status") in ACTIVE_STATUSES
            ]

    # RenderListener ------------------------------------------------------- #

    def queued(self, video_id: int) -> None:
        self._set(video_id, status=VideoStatus.QUEUED, progress=0.0, message="En cola", phase="queued")
        self._videos.update(video_id, status=VideoStatus.QUEUED)

    def started(self, video_id: int) -> None:
        self._set(video_id, status=VideoStatus.RUNNING, progress=0.01, message="Arrancando…")
        self._videos.update(video_id, status=VideoStatus.RUNNING)

    def progressed(self, video_id: int, progress: float, message: str, phase: str) -> None:
        self._set(video_id, progress=round(float(progress), 3), message=message, phase=phase)

    def finished(self, video_id: int, result: RenderResult) -> None:
        self._set(video_id, status=VideoStatus.DONE, progress=1.0, message="Listo", output=result.output)
        self._videos.update(
            video_id, status=VideoStatus.DONE, filename=result.output,
            duration=result.duration, size_mb=result.size_mb,
            captions=result.captions, error=None,
        )

    def failed(self, video_id: int, detail: str) -> None:
        self._set(video_id, status=VideoStatus.ERROR, message=detail)
        self._videos.update(video_id, status=VideoStatus.ERROR, error=detail)

    def _set(self, video_id: int, **fields) -> None:
        with self._lock:
            self._state.setdefault(video_id, {}).update(fields)
