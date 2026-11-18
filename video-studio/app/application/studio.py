"""La aplicación entera, ya conectada a sus puertos: lo que la API recibe."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.outcomes import job_outcome
from app.application.ports import EventLog
from app.application.render_jobs import RenderJobs
from app.application.use_cases.animations import AnimationUseCases
from app.application.use_cases.backgrounds import BackgroundUseCases
from app.application.use_cases.characters import CharacterUseCases
from app.application.use_cases.cover import CoverUseCases
from app.application.use_cases.description import DescriptionUseCases
from app.application.use_cases.illustrations import IllustrationUseCases, ImageSettings
from app.application.use_cases.library import LibraryUseCases
from app.application.use_cases.music import MusicUseCases
from app.application.use_cases.preview import PreviewUseCase
from app.application.use_cases.prompts import PromptBook
from app.application.use_cases.render import RenderUseCases
from app.application.use_cases.scripts import ScriptUseCases
from app.application.use_cases.storyboard import StoryboardUseCases
from app.application.use_cases.voice_takes import VoiceTakeUseCases
from app.application.use_cases.writer_settings import WriterSettings


@dataclass(frozen=True)
class Studio:
    writer: WriterSettings
    scripts: ScriptUseCases
    backgrounds: BackgroundUseCases
    music: MusicUseCases
    preview: PreviewUseCase
    render: RenderUseCases
    library: LibraryUseCases
    jobs: RenderJobs
    events: EventLog
    images: ImageSettings
    illustrations: IllustrationUseCases
    animations: AnimationUseCases
    storyboards: StoryboardUseCases
    characters: CharacterUseCases
    cover: CoverUseCases
    description: DescriptionUseCases
    takes: VoiceTakeUseCases
    #: Dónde está el motor, para poder situarlo si algo falla.
    generator: str
    #: Los prompts que se mandan a los modelos, con las ediciones del usuario.
    prompts: PromptBook = field(default_factory=PromptBook)

    def outcome(self, job: str) -> dict:
        """Desenlace de un trabajo encolado de cualquier tipo."""
        return job_outcome(self.events, job)
