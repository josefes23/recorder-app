"""Encolar un render y seguir cómo va."""

from __future__ import annotations

from collections.abc import Mapping

from app.application.ports import RenderQueue, VideoRepository
from app.application.render_jobs import RenderJobs
from app.domain.cover import read_cover
from app.domain.description import clean_description
from app.domain.errors import NotFoundError, ValidationError
from app.domain.scene import Scene
from app.domain.script import clean_script, estimate_seconds
from app.domain.video import NewVideo, RenderSpec


class RenderUseCases:
    def __init__(self, videos: VideoRepository, queue: RenderQueue, jobs: RenderJobs) -> None:
        self._videos = videos
        self._queue = queue
        self._jobs = jobs

    def start(
        self,
        topic: str,
        script: str,
        voice: str,
        rate: str,
        pitch: str,
        style: dict,
        scenes: list[Scene],
        cover: Mapping | None = None,
        description: str = "",
    ) -> tuple[int, float]:
        """
        Abre la ficha, encola el trabajo y devuelve (id, segundos estimados).
        La portada y la descripción se guardan con la ficha para recuperarlas
        al publicar.
        """
        text = clean_script(script)
        if not text:
            raise ValidationError("El guion está vacío.")

        scene_dicts = [scene.as_dict() for scene in scenes]
        video_id = self._videos.add(
            NewVideo(
                topic, text, voice, style, scene_dicts, read_cover(cover), clean_description(description),
            )
        )
        self._queue.enqueue(
            video_id,
            RenderSpec(topic=topic, script=text, voice=voice, rate=rate, pitch=pitch,
                       style=style, scenes=scene_dicts),
        )
        return video_id, round(estimate_seconds(text), 1)

    def status(self, video_id: int) -> dict:
        """La ficha del historial con el progreso en vivo por encima.

        El progreso solo existe mientras la cola tiene el trabajo en memoria;
        para todo lo demás (lo renderizado antes del último arranque) el
        estado que vale es el del historial.
        """
        record = self._videos.get(video_id)
        if record is None:
            raise NotFoundError("No existe ese video.")
        live = self._jobs.status(video_id) or {}
        return {**record.as_dict(), **live, "id": video_id}

    def active(self) -> list[dict]:
        return self._jobs.all_active()
