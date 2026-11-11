"""
Raíz de composición: el único sitio que conoce a la vez `application` e
`infrastructure`. Elige cada adaptador real, los enchufa a los casos de uso y
arranca los hilos de fondo.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from app.application.consumers import EventConsumer
from app.application.render_jobs import RenderJobs
from app.application.studio import Studio
from app.application.use_cases.backgrounds import BackgroundUseCases
from app.application.use_cases.characters import CONSUMER_GROUP as REFERENCER_GROUP
from app.application.use_cases.characters import CharacterUseCases
from app.application.use_cases.illustrations import CONSUMER_GROUP as ILLUSTRATOR_GROUP
from app.application.use_cases.illustrations import IllustrationUseCases, ImageSettings, ReviewedPainter
from app.application.use_cases.library import LibraryUseCases
from app.application.use_cases.preview import PreviewUseCase
from app.application.use_cases.render import RenderUseCases
from app.application.use_cases.scripts import CONSUMER_GROUP, ScriptUseCases
from app.application.use_cases.storyboard import CONSUMER_GROUP as STORYBOARD_GROUP
from app.application.use_cases.storyboard import StoryboardUseCases
from app.application.use_cases.writer_settings import WriterSettings
from app.domain.events import (
    ILLUSTRATION_REQUESTED,
    REFERENCE_REQUESTED,
    SCRIPT_REQUESTED,
    STORYBOARD_REQUESTED,
)
from app.infrastructure.backgrounds import FileBackgroundStore
from app.infrastructure.env_credentials import HOME_ENV_FILES, EnvCredentials
from app.infrastructure.files import LocalVideoFiles
from app.infrastructure.generator import GeneratorTemplate, load_generator
from app.infrastructure.imaging.illustrator import HttpIllustrator
from app.infrastructure.llm.composer import HttpScriptComposer
from app.infrastructure.paths import Paths
from app.infrastructure.pexels import PexelsLibrary
from app.infrastructure.preview import GeneratorPreviewer
from app.infrastructure.references import FileReferenceStore
from app.infrastructure.render_queue import SubprocessRenderQueue
from app.infrastructure.sqlite import (
    Database,
    SqliteCharacterRepository,
    SqliteEventLog,
    SqliteVideoRepository,
)

#: Imágenes que se pintan a la vez. Un guion pide varias y una a una se haría
#: largo; más de tres choca con los límites por minuto de los generadores.
ILLUSTRATOR_WORKERS = 3


@dataclass
class Container:
    studio: Studio
    paths: Paths
    #: Arranca los hilos de fondo. Lo llama el `lifespan` de la app, no el import.
    workers: list[Callable[[], object]] = field(default_factory=list)
    _started: bool = field(default=False, init=False)

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for start in self.workers:
            start()


def build_container(paths: Paths | None = None) -> Container:
    paths = paths or Paths.default()
    gen = load_generator(paths.generator)

    database = Database(paths.database)
    videos = SqliteVideoRepository(database)
    events = SqliteEventLog(database)

    # La clave de Pexels vive en el .env del generador, donde ya la usa su script.
    credentials = EnvCredentials(paths.env_file, extra_files=(paths.generator_env, *HOME_ENV_FILES))
    composer = HttpScriptComposer()
    writer = WriterSettings(credentials, composer)
    scripts = ScriptUseCases(events, writer, composer, GeneratorTemplate(gen))

    jobs = RenderJobs(videos)
    queue = SubprocessRenderQueue(paths.jobs, paths.outputs, paths.root, listener=jobs)

    store = FileBackgroundStore(paths.backgrounds, paths.thumbs)
    images = ImageSettings(credentials)
    character_library = SqliteCharacterRepository(database)
    references = FileReferenceStore(paths.references)
    painter = ReviewedPainter(images, HttpIllustrator(), writer, composer)
    illustrations = IllustrationUseCases(events, images, painter, store, character_library, references)
    characters = CharacterUseCases(events, character_library, references, images, painter)
    storyboards = StoryboardUseCases(events, writer, composer, character_library)

    studio = Studio(
        writer=writer,
        scripts=scripts,
        backgrounds=BackgroundUseCases(
            store,
            PexelsLibrary(lambda: credentials.get("PEXELS_API_KEY")),
        ),
        preview=PreviewUseCase(GeneratorPreviewer(gen, paths.backgrounds, paths.previews)),
        render=RenderUseCases(videos, queue, jobs),
        library=LibraryUseCases(videos, LocalVideoFiles()),
        jobs=jobs,
        events=events,
        images=images,
        illustrations=illustrations,
        storyboards=storyboards,
        characters=characters,
        generator=str(paths.generator),
    )

    consumer = EventConsumer(events, CONSUMER_GROUP, (SCRIPT_REQUESTED,), scripts.handle_request)
    storyboarder = EventConsumer(events, STORYBOARD_GROUP, (STORYBOARD_REQUESTED,), storyboards.handle_request)
    referencer = EventConsumer(events, REFERENCER_GROUP, (REFERENCE_REQUESTED,), characters.handle_request)

    # Consumidores que compiten: cada uno lee todos los encargos con su propio
    # grupo y `claim` decide quién pinta cada imagen. Así se pintan varias a la
    # vez sin repetir ninguna, con las mismas piezas que el guion.
    illustrators = [
        EventConsumer(
            events, f"{ILLUSTRATOR_GROUP}-{n}", (ILLUSTRATION_REQUESTED,), illustrations.handle_request,
        )
        for n in range(1, ILLUSTRATOR_WORKERS + 1)
    ]

    def start_consumers() -> None:
        events.prune()
        threading.Thread(target=consumer.run_forever, daemon=True, name="script-consumer").start()
        threading.Thread(target=storyboarder.run_forever, daemon=True, name="storyboard-consumer").start()
        threading.Thread(target=referencer.run_forever, daemon=True, name="reference-consumer").start()
        for n, illustrator in enumerate(illustrators, start=1):
            threading.Thread(target=illustrator.run_forever, daemon=True, name=f"illustrator-{n}").start()

    return Container(studio=studio, paths=paths, workers=[queue.start, start_consumers])
