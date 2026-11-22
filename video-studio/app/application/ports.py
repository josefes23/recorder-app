"""
Puertos: lo que la aplicación necesita del mundo y lo que ofrece a quien la
llama desde fuera del hilo de la petición.

Son Protocols a propósito: la implementación real vive en `infrastructure` y no
hereda de nada de aquí; basta con que tenga los mismos métodos.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol

from app.domain.animation import GeneratedClip, VideoProvider
from app.domain.background import Background
from app.domain.cover import CoverWord
from app.domain.events import Event
from app.domain.illustration import Character, GeneratedImage, ImageProvider
from app.domain.music import Track
from app.domain.production import VERTICAL, Format
from app.domain.saved_characters import SavedCharacter
from app.domain.stock import StockClip
from app.domain.style import CaptionStyle
from app.domain.video import NewVideo, RenderResult, RenderSpec, Video
from app.domain.voice import Voice
from app.domain.voice_take import TakeRequest, VoiceTake
from app.domain.writer import Provider


class VideoRepository(Protocol):
    """Historial de videos."""

    def add(self, video: NewVideo) -> int: ...
    def update(self, video_id: int, **fields) -> None: ...
    def get(self, video_id: int) -> Video | None: ...
    def list(self, limit: int = 60) -> list[Video]: ...
    def remove(self, video_id: int) -> None: ...


class EventLog(Protocol):
    """
    Log append-only con posiciones y consumidores que confirman avance.

    Las garantías que la aplicación da por hechas: el log solo crece, el offset
    es monótono, la entrega es al menos una vez y `claim` excluye a otros
    procesos sobre la misma clave.
    """

    def publish(self, topic: str, key: str | None, payload: dict) -> Event: ...
    def read_after(self, offset: int, topics: tuple[str, ...] = (), limit: int = 200) -> list[Event]: ...
    def wait_for(self, offset: int, timeout: float, topics: tuple[str, ...] = ()) -> list[Event]: ...
    def last_offset(self) -> int: ...
    def by_key(self, key: str, topics: tuple[str, ...] = ()) -> list[Event]: ...
    def settled(self, key: str, topics: tuple[str, ...]) -> bool: ...
    def claim(self, key: str) -> bool: ...
    def committed_offset(self, consumer_group: str) -> int: ...
    def commit(self, consumer_group: str, offset: int) -> None: ...
    def prune(self) -> int: ...


class RenderListener(Protocol):
    """
    Puerto de entrada: por aquí la cola de renders informa de cómo va cada
    trabajo. Lo implementa la aplicación (`RenderJobs`), no la infraestructura.
    """

    def queued(self, video_id: int) -> None: ...
    def started(self, video_id: int) -> None: ...
    def progressed(self, video_id: int, progress: float, message: str, phase: str) -> None: ...
    def finished(self, video_id: int, result: RenderResult) -> None: ...
    def failed(self, video_id: int, detail: str) -> None: ...


class RenderQueue(Protocol):
    """Encola renders y los ejecuta uno a uno, avisando al `RenderListener`."""

    def enqueue(self, video_id: int, spec: RenderSpec) -> None: ...


class Readable(Protocol):
    """Lo mínimo que hace falta para copiar bytes a disco: un archivo subido o una descarga."""

    def read(self, size: int = -1, /) -> bytes: ...


class BackgroundStore(Protocol):
    """La galería de fondos y sus miniaturas."""

    def list(self) -> list[Background]: ...
    def has(self, name: str) -> bool: ...
    def path(self, name: str) -> Path | None: ...
    #: Los bytes del fondo, o None si no está: para corregir una imagen generada.
    def read(self, name: str) -> bytes | None: ...
    def save(self, name: str, stream: Readable) -> str: ...
    def remove(self, name: str) -> None: ...
    def thumbnail_path(self, thumb: str) -> Path | None: ...


class MusicStore(Protocol):
    """La galería de música: pistas que subió el usuario."""

    def list(self) -> list[Track]: ...
    def path(self, name: str) -> Path | None: ...
    def save(self, name: str, stream: Readable) -> str: ...
    def remove(self, name: str) -> None: ...


class StockLibrary(Protocol):
    """Catálogo de clips de stock: buscar, situar uno por su id y abrirlo para bajarlo."""

    #: `orientation`: «portrait» para videos verticales, «landscape» para horizontales.
    def search(self, query: str, orientation: str = "portrait") -> list[StockClip]: ...
    def clip(self, clip_id: int, orientation: str = "portrait") -> StockClip: ...
    def open(self, clip: StockClip) -> AbstractContextManager[Readable]: ...


class FramePreviewer(Protocol):
    """Compone un fotograma con fondo y subtítulo en el formato del video. Devuelve un PNG."""

    def render(
        self, text: str, style: CaptionStyle, background: str | None, topic: str, fmt: Format = VERTICAL,
    ) -> bytes: ...


class CoverPainter(Protocol):
    """
    Pinta la portada a tamaño completo (`size`: 1080x1920 en vertical, 1280x720
    en horizontal) y devuelve un JPEG.

    `background` es el archivo de la galería, imagen o clip; None pinta el
    degradado del tema, el mismo que usa el motor cuando no hay fondo.

    Con `width`, el JPEG sale reducido a ese ancho: la letra está medida para el
    tamaño completo, así que se pinta grande y se reduce al final.
    """

    def paint(
        self,
        words: Sequence[CoverWord],
        design: str,
        background: Path | None,
        topic: str,
        size: tuple[int, int] = (1080, 1920),
        width: int | None = None,
    ) -> bytes: ...


class VoiceSynthesizer(Protocol):
    """
    Genera la voz del guion (edge-tts, con el motor) y devuelve el audio MP3,
    las marcas de cada palabra ({text, start, end}) y la duración en segundos.
    Con voces por personaje, cada intervención con la suya, unidas en una pista.
    """

    def synthesize(self, request: TakeRequest) -> tuple[bytes, list[dict], float]: ...


class RemoteVoices(Protocol):
    """Las voces de una cuenta de pago (ElevenLabs): consultarlas gasta una llamada, no créditos."""

    def ready(self) -> bool: ...
    def voices(self) -> list[Voice]: ...


class TakeStore(Protocol):
    """
    Las tomas de voz, por clave. Las marcas se guardan siempre (pesan poco y
    dicen los tiempos reales de cada video); el audio, solo el de las últimas.
    """

    def get(self, key: str) -> VoiceTake | None: ...
    def audio(self, key: str) -> Path | None: ...
    def save(self, key: str, audio: bytes, words: list[dict], duration: float) -> VoiceTake: ...


class PosterStore(Protocol):
    """
    La portada de cada video en pequeño, para la cuadrícula de la biblioteca.
    Se pinta una vez y se guarda: la portada de un video no cambia después.
    """

    def read(self, video_id: int) -> bytes | None: ...
    def save(self, video_id: int, data: bytes) -> None: ...
    def remove(self, video_id: int) -> None: ...


class ScriptTemplate(Protocol):
    """La plantilla local: un guion genérico sin pedirle nada a ningún modelo."""

    def template(self, topic: str) -> str: ...


class ScriptComposer(Protocol):
    """
    Habla con el proveedor que toque: redacta y ofrece su catálogo de modelos.

    Con `image`, el modelo la ve junto al encargo; solo se manda a proveedores
    que ven imágenes (`Provider.sees_images`).
    """

    def compose(
        self,
        provider: Provider,
        model: str,
        api_key: str | None,
        system: str,
        prompt: str,
        image: GeneratedImage | None = None,
    ) -> str: ...
    def catalog(self, provider: Provider, api_key: str | None) -> list[dict]: ...


class Illustrator(Protocol):
    """
    Pinta una imagen (vertical u horizontal según `aspect`) a partir de un encargo de texto, con el
    generador y el modelo que toquen. Los fallos llegan como `DomainError` con
    el motivo ya redactado: sin cupo, clave mala, imagen bloqueada…

    La semilla y las imágenes de referencia (`references`, en el orden en
    que las nombra el encargo) las respeta quien pueda; quien no, las ignora.
    """

    def illustrate(
        self,
        provider: ImageProvider,
        model: str,
        credentials: Mapping[str, str | None],
        prompt: str,
        seed: int | None = None,
        references: Sequence[GeneratedImage] = (),
        aspect: str = "9:16",
    ) -> GeneratedImage: ...


class Animator(Protocol):
    """
    Anima una imagen: la toma como primer fotograma y devuelve un clip vertical
    de `seconds` segundos. Tarda minutos, así que solo lo llama el consumidor
    de encargos. Los fallos llegan como `DomainError` con el motivo redactado.
    """

    def animate(
        self,
        provider: VideoProvider,
        model: str,
        credentials: Mapping[str, str | None],
        image: GeneratedImage,
        prompt: str,
        seconds: int,
        aspect: str = "9:16",
    ) -> GeneratedClip: ...


class CharacterRepository(Protocol):
    """
    La biblioteca de elementos que se repiten entre videos. El nombre es la
    clave: sin tildes ni mayúsculas, «Lucía» y «lucia» son el mismo.
    """

    def list(self) -> list[SavedCharacter]: ...
    def get(self, character_id: int) -> SavedCharacter | None: ...
    def find(self, name: str) -> SavedCharacter | None: ...
    def upsert(self, character: Character) -> SavedCharacter: ...
    def set_reference(self, character_id: int, reference: str | None) -> None: ...
    def remove(self, character_id: int) -> None: ...


class ReferenceStore(Protocol):
    """Las imágenes de referencia de la biblioteca, por nombre de archivo."""

    def save(self, name: str, data: bytes) -> str: ...
    def read(self, name: str) -> bytes | None: ...
    def path(self, name: str) -> Path | None: ...
    def remove(self, name: str) -> None: ...


class CredentialStore(Protocol):
    """Dónde viven las claves y los ajustes del redactor."""

    def get(self, name: str) -> str | None: ...
    def save(self, values: Mapping[str, str | None]) -> None: ...


class PromptStore(Protocol):
    """Los prompts que el usuario ha editado; los demás usan el original."""

    def all(self) -> dict[str, str]: ...
    def set(self, prompt_id: str, body: str) -> None: ...
    def remove(self, prompt_id: str) -> None: ...


class VideoFiles(Protocol):
    """Los archivos de video ya renderizados."""

    def exists(self, path: Path) -> bool: ...
    def remove(self, path: Path) -> None: ...
