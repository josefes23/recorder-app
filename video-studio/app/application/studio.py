"""La aplicación entera, ya conectada a sus puertos: lo que la API recibe."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports import EventLog
from app.application.render_jobs import RenderJobs
from app.application.use_cases.backgrounds import BackgroundUseCases
from app.application.use_cases.library import LibraryUseCases
from app.application.use_cases.preview import PreviewUseCase
from app.application.use_cases.render import RenderUseCases
from app.application.use_cases.scripts import ScriptUseCases
from app.application.use_cases.writer_settings import WriterSettings


@dataclass(frozen=True)
class Studio:
    writer: WriterSettings
    scripts: ScriptUseCases
    backgrounds: BackgroundUseCases
    preview: PreviewUseCase
    render: RenderUseCases
    library: LibraryUseCases
    jobs: RenderJobs
    events: EventLog
    #: Dónde está el motor, para poder situarlo si algo falla.
    generator: str
