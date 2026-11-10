"""Dobles en memoria de los puertos de `app.application.ports`."""

from __future__ import annotations

import io
from dataclasses import replace
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import BinaryIO

from app.application.render_jobs import RenderJobs
from app.application.studio import Studio
from app.application.use_cases.backgrounds import BackgroundUseCases
from app.application.use_cases.library import LibraryUseCases
from app.application.use_cases.preview import PreviewUseCase
from app.application.use_cases.render import RenderUseCases
from app.application.use_cases.scripts import ScriptUseCases
from app.application.use_cases.writer_settings import WriterSettings
from app.domain.background import Background
from app.domain.errors import EngineError, NotFoundError
from app.domain.events import Event
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
            created_at="2026-01-01T00:00:00",
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
        event = Event(len(self.events) + 1, topic, key, payload, "2026-01-01T00:00:00")
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
    def __init__(self, text: str = LONG_SCRIPT, error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[tuple] = []

    def compose(self, provider: Provider, model: str, api_key: str | None, system: str, prompt: str) -> str:
        self.calls.append((provider.id, model, api_key, system, prompt))
        if self.error:
            raise self.error
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

    def save(self, name: str, stream: BinaryIO) -> str:
        self.saved.append(name)
        self.items.append(Background.describe(name, 0.0, len(stream.read()), None))
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


class FakePreviewer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, CaptionStyle, str | None, str]] = []

    def render(self, text: str, style: CaptionStyle, background: str | None, topic: str) -> bytes:
        self.calls.append((text, style, background, topic))
        return b"\x89PNG" + text.encode()


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
    studio = Studio(
        writer=writer,
        scripts=ScriptUseCases(events, writer, composer, FakeTemplate()),
        backgrounds=BackgroundUseCases(backgrounds, stock),
        preview=PreviewUseCase(previewer),
        render=RenderUseCases(videos, queue, jobs),
        library=LibraryUseCases(videos, files),
        jobs=jobs,
        events=events,
        generator="/fake/auto-video-generator",
    )
    fakes = SimpleNamespace(
        videos=videos, events=events, credentials=credentials, composer=composer,
        queue=queue, files=files, backgrounds=backgrounds, stock=stock, previewer=previewer, jobs=jobs,
    )
    return studio, fakes
