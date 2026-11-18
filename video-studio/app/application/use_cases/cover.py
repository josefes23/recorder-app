"""
La portada: pintarla con lo que haya en pantalla, proponer títulos gancho y
devolver la de cualquier video ya renderizado.

Pintar es local y tarda menos de un segundo, así que se resuelve en la misma
petición, como la previsualización. Los títulos los escribe el modelo del
guion y van por el flujo de eventos, por lo mismo que el guion: el modelo
puede tardar más de lo que aguanta una petición.
"""

from __future__ import annotations

from app.application.ports import (
    BackgroundStore,
    CoverPainter,
    EventLog,
    PosterStore,
    ScriptComposer,
    VideoRepository,
)
from app.application.use_cases.writer_settings import WriterSettings
from app.domain.cover import (
    TITLES_SYSTEM_PROMPT,
    Cover,
    build_titles_prompt,
    cover_filename,
    cover_words,
    parse_titles,
    stored_cover,
    validate_cover,
)
from app.domain.production import VERTICAL, Format, format_by_id, format_of
from app.domain.errors import DomainError, NotFoundError, ValidationError, WriterError
from app.domain.events import (
    TITLES_COMPLETED,
    TITLES_FAILED,
    TITLES_REQUESTED,
    TITLES_TERMINAL,
    Event,
    new_job_key,
)
from app.domain.script import clean_script

CONSUMER_GROUP = "titler"


class CoverUseCases:
    def __init__(
        self,
        events: EventLog,
        writer: WriterSettings,
        composer: ScriptComposer,
        painter: CoverPainter,
        store: BackgroundStore,
        videos: VideoRepository,
        posters: PosterStore,
    ) -> None:
        self._events = events
        self._writer = writer
        self._composer = composer
        self._painter = painter
        self._store = store
        self._videos = videos
        self._posters = posters

    # Desde la API ------------------------------------------------------------ #

    def paint(self, title: str, design: str, background: str | None, topic: str, format: str = "9:16") -> bytes:
        """La portada tal como está ahora en el estudio, del tamaño de su formato."""
        return self._paint(validate_cover(title, design, background), topic, format_by_id(format))

    def of_video(self, video_id: int) -> tuple[bytes, str]:
        """La portada guardada con ese video y el nombre con que se descarga."""
        record = self._videos.get(video_id)
        if record is None:
            raise NotFoundError("No existe ese video.")
        cover = stored_cover(record.cover, record.topic, record.scenes or [])
        return self._paint(cover, record.topic, format_of(record.style)), cover_filename(record.topic)

    def poster_of_video(self, video_id: int) -> bytes:
        """
        La portada del video en pequeño, para la cuadrícula de la biblioteca.
        La primera vez se pinta y se guarda; después sale del disco, porque la
        portada de un video no cambia una vez renderizado. Así abrir la
        biblioteca no pinta decenas de portadas a tamaño completo.
        """
        record = self._videos.get(video_id)
        if record is None:
            raise NotFoundError("No existe ese video.")
        cached = self._posters.read(video_id)
        if cached is not None:
            return cached
        fmt = format_of(record.style)
        cover = stored_cover(record.cover, record.topic, record.scenes or [])
        jpeg = self._paint(cover, record.topic, fmt, width=fmt.poster_width)
        self._posters.save(video_id, jpeg)
        return jpeg

    def request_titles(self, topic: str, script: str) -> Event:
        """Encola la propuesta de títulos y devuelve el evento con la clave del trabajo."""
        text = clean_script(script)
        if not text and not topic.strip():
            raise ValidationError("Escribe primero el tema o el guion: los títulos salen de ahí.")
        if not self._writer.available():
            raise ValidationError(
                "Los títulos los propone el modelo del guion: añade una clave en «Modelo del guion», "
                "o escribe el tuyo."
            )
        return self._events.publish(
            TITLES_REQUESTED, new_job_key("tt"), {"topic": topic.strip(), "script": text}
        )

    # Desde el consumidor ------------------------------------------------------ #

    def suggest(self, topic: str, script: str) -> list[str]:
        """Propone títulos ahora, bloqueando. Lo llama el consumidor, nunca la API."""
        provider = self._writer.active()
        if provider is None:
            raise WriterError("No hay clave de API configurada. Añade una en «Modelo del guion».")
        raw = self._composer.compose(
            provider,
            self._writer.model_for(provider),
            self._writer.api_key(provider),
            TITLES_SYSTEM_PROMPT,
            build_titles_prompt(topic, script),
        )
        return parse_titles(raw)

    def handle_request(self, event: Event) -> None:
        """Atiende un `titles.requested` y publica su desenlace."""
        # Las mismas garantías que el guion: llegar dos veces no cuesta dos llamadas.
        if event.key is None or self._events.settled(event.key, TITLES_TERMINAL):
            return
        if not self._events.claim(event.key):
            return
        try:
            titles = self.suggest(event.payload.get("topic", ""), event.payload.get("script", ""))
        except DomainError as exc:
            self._events.publish(TITLES_FAILED, event.key, {"detail": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 - el consumidor no debe morir nunca
            self._events.publish(TITLES_FAILED, event.key, {"detail": f"{type(exc).__name__}: {exc}"})
            return
        self._events.publish(TITLES_COMPLETED, event.key, {"titles": titles})

    # ------------------------------------------------------------------------ #

    def _paint(self, cover: Cover, topic: str, fmt: Format = VERTICAL, width: int | None = None) -> bytes:
        # Un fondo que ya no está en la galería no tumba la portada: sale el
        # degradado del tema, como en un render sin fondo.
        path = self._store.path(cover.background) if cover.background else None
        return self._painter.paint(
            cover_words(cover.title), cover.design, path, topic or cover.title, fmt.cover_size, width,
        )
