"""Dobles en memoria de los puertos de `app.application.ports`."""

from __future__ import annotations

import io
from datetime import datetime
from dataclasses import replace
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import BinaryIO

from app.application.render_jobs import RenderJobs
from app.application.studio import Studio
from app.application.use_cases.animations import AnimationUseCases
from app.application.use_cases.backgrounds import BackgroundUseCases
from app.application.use_cases.characters import CharacterUseCases
from app.application.use_cases.cover import CoverUseCases
from app.application.use_cases.description import DescriptionUseCases
from app.application.use_cases.illustrations import IllustrationUseCases, ImageSettings, ReviewedPainter
from app.application.use_cases.library import LibraryUseCases
from app.application.use_cases.preview import PreviewUseCase
from app.application.use_cases.render import RenderUseCases
from app.application.use_cases.scripts import ScriptUseCases
from app.application.use_cases.storyboard import StoryboardUseCases
from app.application.use_cases.writer_settings import WriterSettings
from app.domain.animation import GeneratedClip
from app.domain.background import Background
from app.domain.cover import CoverWord
from app.domain.errors import EngineError, NotFoundError
from app.domain.events import Event
from app.domain.illustration import Character, GeneratedImage, ImageProvider, fold
from app.domain.saved_characters import SavedCharacter, is_reference_name
from app.domain.stock import StockClip
from app.domain.style import CaptionStyle
from app.domain.video import NewVideo, RenderSpec, Video
from app.domain.writer import Provider

# Un guion que pasa la validación (≥ 50 palabras).
LONG_SCRIPT = " ".join(f"palabra{i}" for i in range(90))


class InMemoryVideoRepository:
    def __init__(self) -> None:
        self._rows: dict[int, Video] = {}
        self._next = 1

    def add(self, video: NewVideo) -> int:
        vid = self._next
        self._next += 1
        self._rows[vid] = Video(
            id=vid, topic=video.topic, script=video.script, voice=video.voice,
            style=video.style, scenes=video.scenes, filename=None, duration=None,
            size_mb=None, captions=None, status="queued", error=None,
            created_at="2026-01-01T00:00:00", cover=video.cover,
            description=video.description,
        )
        return vid

    def update(self, video_id: int, **fields) -> None:
        clean = {k: (str(v) if isinstance(v, Enum) else v) for k, v in fields.items()}
        self._rows[video_id] = replace(self._rows[video_id], **clean)

    def get(self, video_id: int) -> Video | None:
        return self._rows.get(video_id)

    def list(self, limit: int = 60) -> list[Video]:
        return sorted(self._rows.values(), key=lambda v: -v.id)[:limit]

    def remove(self, video_id: int) -> None:
        self._rows.pop(video_id, None)


class InMemoryEventLog:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self.offsets: dict[str, int] = {}
        self.claims: set[str] = set()

    def publish(self, topic: str, key: str | None, payload: dict) -> Event:
        # Hora local, como el log de SQLite: los reintentos de imagen la miran.
        event = Event(len(self.events) + 1, topic, key, payload, datetime.now().isoformat(timespec="seconds"))
        self.events.append(event)
        return event

    def read_after(self, offset: int, topics: tuple[str, ...] = (), limit: int = 200) -> list[Event]:
        return [
            e for e in self.events if e.offset > offset and (not topics or e.topic in topics)
        ][:limit]

    def wait_for(self, offset: int, timeout: float, topics: tuple[str, ...] = ()) -> list[Event]:
        return self.read_after(offset, topics)

    def last_offset(self) -> int:
        return len(self.events)

    def by_key(self, key: str, topics: tuple[str, ...] = ()) -> list[Event]:
        return [e for e in self.events if e.key == key and (not topics or e.topic in topics)]

    def settled(self, key: str, topics: tuple[str, ...]) -> bool:
        return bool(self.by_key(key, topics))

    def claim(self, key: str) -> bool:
        if key in self.claims:
            return False
        self.claims.add(key)
        return True

    def committed_offset(self, consumer_group: str) -> int:
        return self.offsets.get(consumer_group, 0)

    def commit(self, consumer_group: str, offset: int) -> None:
        self.offsets[consumer_group] = offset

    def prune(self) -> int:
        return 0


class FakeComposer:
    """
    Contesta `text` a todo, o falla con `error`. Con `replies`, contesta esas
    respuestas en orden —una excepción en la lista se lanza— y después `text`.
    """

    def __init__(
        self, text: str = LONG_SCRIPT, error: Exception | None = None, replies: list | None = None
    ) -> None:
        self.text = text
        self.error = error
        self.replies = list(replies or [])
        self.calls: list[tuple] = []
        #: Las imágenes que se le enseñaron, en orden.
        self.images: list[GeneratedImage] = []

    def compose(
        self,
        provider: Provider,
        model: str,
        api_key: str | None,
        system: str,
        prompt: str,
        image: GeneratedImage | None = None,
    ) -> str:
        self.calls.append((provider.id, model, api_key, system, prompt))
        if image is not None:
            self.images.append(image)
        if self.error:
            raise self.error
        if self.replies:
            reply = self.replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        return self.text

    def catalog(self, provider: Provider, api_key: str | None) -> list[dict]:
        return [{"id": provider.default_model, "label": provider.default_model, "group": "Modelos"}]


class DictCredentials:
    def __init__(self, **values: str) -> None:
        self.values: dict[str, str] = dict(values)

    def get(self, name: str) -> str | None:
        return self.values.get(name) or None

    def save(self, values) -> None:
        for name, value in values.items():
            if value is None:
                self.values.pop(name, None)
            else:
                self.values[name] = value


class FakeQueue:
    def __init__(self, listener) -> None:
        self._listener = listener
        self.enqueued: list[tuple[int, RenderSpec]] = []

    def enqueue(self, video_id: int, spec: RenderSpec) -> None:
        self.enqueued.append((video_id, spec))
        self._listener.queued(video_id)


class FakeTemplate:
    def template(self, topic: str) -> str:
        return f"## Hoy hablamos de *{topic}*.  Primera idea, segunda idea."


class FakeFiles:
    def __init__(self, existing: tuple[str, ...] = ()) -> None:
        self.existing = {Path(p) for p in existing}
        self.removed: list[Path] = []

    def exists(self, path: Path) -> bool:
        return path in self.existing

    def remove(self, path: Path) -> None:
        self.removed.append(path)
        self.existing.discard(path)


class FakeBackgroundStore:
    def __init__(self) -> None:
        self.items = [Background.describe("bosque_1.mp4", 12.3, 4_200_000, "abc.jpg")]
        self.saved: list[str] = []
        #: Lo que se guardó con cada nombre.
        self.data: dict[str, bytes] = {}
        self.removed: list[str] = []
        self.thumbs = {"abc.jpg": Path("/thumbs/abc.jpg")}

    def list(self) -> list[Background]:
        return list(self.items)

    def remove(self, name: str) -> None:
        self.removed.append(name)
        self.items = [item for item in self.items if item.name != name]

    def has(self, name: str) -> bool:
        return any(item.name == name for item in self.items)

    def path(self, name: str) -> Path | None:
        return Path("/bg") / name if self.has(name) else None

    def read(self, name: str) -> bytes | None:
        return self.data.get(name, b"bytes de " + name.encode()) if self.has(name) else None

    def save(self, name: str, stream: BinaryIO) -> str:
        self.saved.append(name)
        self.data[name] = stream.read()
        self.items.append(Background.describe(name, 0.0, len(self.data[name]), None))
        return name

    def thumbnail_path(self, thumb: str) -> Path | None:
        return self.thumbs.get(thumb)


class FakeStockLibrary:
    """Un catálogo de dos clips. La descarga de los ids en `broken` falla."""

    def __init__(self) -> None:
        self.clips = {
            11: StockClip(11, "https://img/11.jpg", 12, 1080, 1920, 3.4, "Ana", "https://pexels/11",
                          link="https://cdn/11.mp4"),
            12: StockClip(12, "https://img/12.jpg", 9, 1080, 1920, 2.1, "Luis", "https://pexels/12",
                          link="https://cdn/12.mp4"),
        }
        self.searched: list[str] = []
        self.broken: set[int] = set()

    def search(self, query: str) -> list[StockClip]:
        self.searched.append(query)
        return list(self.clips.values())

    def clip(self, clip_id: int) -> StockClip:
        if clip_id not in self.clips:
            raise NotFoundError(f"Pexels ya no tiene el clip {clip_id}.")
        return self.clips[clip_id]

    def open(self, clip: StockClip) -> io.BytesIO:
        if clip.id in self.broken:
            raise EngineError("Sin conexión con Pexels.")
        return io.BytesIO(b"mp4:" + str(clip.id).encode())


class FakeIllustrator:
    """Pinta un JPEG de mentira, o falla con `error`."""

    def __init__(self, error: Exception | None = None, fail_from: int | None = None) -> None:
        self.error = error
        #: A partir de esa llamada (contando desde 0), falla con `error`.
        self.fail_from = fail_from
        self.calls: list[tuple[str, str, dict, str, int | None]] = []
        self.references: list[list[bytes]] = []

    def illustrate(
        self, provider: ImageProvider, model: str, credentials, prompt: str, seed: int | None = None,
        references=(),
    ) -> GeneratedImage:
        self.calls.append((provider.id, model, dict(credentials), prompt, seed))
        #: Las referencias de cada llamada, en orden.
        self.references.append([r.data for r in references])
        if self.error and (self.fail_from is None or len(self.calls) > self.fail_from):
            raise self.error
        # La semilla va dentro para saber qué intento acabó en la galería.
        return GeneratedImage(b"\xff\xd8jpeg" + str(seed).encode(), ".jpg")


class FakeAnimator:
    """Devuelve un MP4 de mentira, o falla con `error`."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        #: (proveedor, modelo, credenciales, bytes de la imagen, encargo, segundos) de cada llamada.
        self.calls: list[tuple[str, str, dict, bytes, str, int]] = []

    def animate(self, provider, model, credentials, image, prompt, seconds) -> GeneratedClip:
        self.calls.append((provider.id, model, dict(credentials), image.data, prompt, seconds))
        if self.error:
            raise self.error
        return GeneratedClip(b"\x00\x00\x00\x18ftypmp42" + str(seconds).encode())


class InMemoryCharacterRepository:
    def __init__(self) -> None:
        self.rows: dict[int, SavedCharacter] = {}
        self._next = 1
        self._tick = 0

    def _stamp(self) -> str:
        # Cada escritura «más tarde» que la anterior, para que el orden se pueda probar.
        self._tick += 1
        return f"2026-11-11T12:00:{self._tick:02d}"

    def list(self) -> list[SavedCharacter]:
        return sorted(self.rows.values(), key=lambda c: (c.updated_at, c.id), reverse=True)

    def get(self, character_id: int) -> SavedCharacter | None:
        return self.rows.get(character_id)

    def find(self, name: str) -> SavedCharacter | None:
        return next((c for c in self.rows.values() if fold(c.name) == fold(name)), None)

    def upsert(self, character: Character) -> SavedCharacter:
        now = self._stamp()
        found = self.find(character.name)
        if found:
            saved = replace(found, name=character.name, traits=character.traits, kind=character.kind, updated_at=now)
        else:
            saved = SavedCharacter(self._next, character.name, character.traits, character.kind, None, now, now)
            self._next += 1
        self.rows[saved.id] = saved
        return saved

    def set_reference(self, character_id: int, reference: str | None) -> None:
        self.rows[character_id] = replace(self.rows[character_id], reference=reference, updated_at=self._stamp())

    def remove(self, character_id: int) -> None:
        self.rows.pop(character_id, None)


class FakeReferenceStore:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.removed: list[str] = []

    def save(self, name: str, data: bytes) -> str:
        assert is_reference_name(name), name
        self.files[name] = data
        return name

    def read(self, name: str) -> bytes | None:
        return self.files.get(name)

    def path(self, name: str) -> Path | None:
        return Path("/references") / name if name in self.files else None

    def remove(self, name: str) -> None:
        self.removed.append(name)
        self.files.pop(name, None)


class FakePreviewer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, CaptionStyle, str | None, str]] = []

    def render(self, text: str, style: CaptionStyle, background: str | None, topic: str) -> bytes:
        self.calls.append((text, style, background, topic))
        return b"\x89PNG" + text.encode()


class FakeCoverPainter:
    def __init__(self) -> None:
        self.calls: list[tuple[list[CoverWord], str, Path | None, str]] = []

    def paint(self, words, design: str, background: Path | None, topic: str) -> bytes:
        self.calls.append((list(words), design, background, topic))
        return b"\xff\xd8JPEG " + " ".join(w.text for w in words).encode()


def make_studio(credentials: DictCredentials | None = None, composer: FakeComposer | None = None):
    """Un estudio completo sobre dobles. Devuelve (studio, dobles)."""
    videos = InMemoryVideoRepository()
    events = InMemoryEventLog()
    credentials = credentials or DictCredentials()
    composer = composer or FakeComposer()
    writer = WriterSettings(credentials, composer)
    jobs = RenderJobs(videos)
    queue = FakeQueue(jobs)
    files = FakeFiles()
    backgrounds = FakeBackgroundStore()
    stock = FakeStockLibrary()
    previewer = FakePreviewer()
    illustrator = FakeIllustrator()
    images = ImageSettings(credentials)
    character_library = InMemoryCharacterRepository()
    references = FakeReferenceStore()
    painter = ReviewedPainter(images, illustrator, writer, composer)
    animator = FakeAnimator()
    cover_painter = FakeCoverPainter()
    studio = Studio(
        writer=writer,
        scripts=ScriptUseCases(events, writer, composer, FakeTemplate()),
        backgrounds=BackgroundUseCases(backgrounds, stock),
        preview=PreviewUseCase(previewer),
        render=RenderUseCases(videos, queue, jobs),
        library=LibraryUseCases(videos, files),
        jobs=jobs,
        events=events,
        images=images,
        illustrations=IllustrationUseCases(events, images, painter, backgrounds, character_library, references),
        animations=AnimationUseCases(events, credentials, animator, backgrounds),
        storyboards=StoryboardUseCases(events, writer, composer),
        characters=CharacterUseCases(events, character_library, references, images, painter),
        cover=CoverUseCases(events, writer, composer, cover_painter, backgrounds, videos),
        description=DescriptionUseCases(events, writer, composer),
        generator="/fake/auto-video-generator",
    )
    fakes = SimpleNamespace(
        videos=videos, events=events, credentials=credentials, composer=composer,
        queue=queue, files=files, backgrounds=backgrounds, stock=stock, previewer=previewer, jobs=jobs,
        illustrator=illustrator, painter=painter, character_library=character_library, references=references,
        cover_painter=cover_painter, animator=animator,
    )
    return studio, fakes
