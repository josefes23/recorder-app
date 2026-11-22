"""Un fotograma con fondo y subtítulo en vez de un render de cinco minutos."""

from __future__ import annotations

from app.application.ports import FramePreviewer
from app.domain.production import format_by_id
from app.domain.script import clean_script
from app.domain.style import CaptionStyle

SAMPLE_TEXT = "TEXTO DE EJEMPLO"


class PreviewUseCase:
    def __init__(self, previewer: FramePreviewer) -> None:
        self._previewer = previewer

    def frame(
        self, caption: str, style: dict | None, background: str | None, topic: str, format: str = "9:16",
    ) -> bytes:
        text = clean_script(caption).upper() or SAMPLE_TEXT
        return self._previewer.render(
            text, CaptionStyle.from_dict(style), background, topic or "preview", format_by_id(format)
        )
