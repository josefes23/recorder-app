"""Previsualización: un fotograma compuesto con el motor, en vez de un render."""

from __future__ import annotations

import io
import threading
from pathlib import Path
from types import ModuleType

from app.domain.production import VERTICAL, Format
from app.domain.style import CaptionStyle
from app.infrastructure.generator import apply_format, apply_style


class GeneratorPreviewer:
    def __init__(self, gen: ModuleType, background_dir: Path, previews_dir: Path) -> None:
        self._gen = gen
        self._backgrounds = background_dir
        self._previews = previews_dir
        # El estilo se aplica sobre constantes del generador, que son globales
        # del proceso: solo puede haber una previsualización componiendo a la
        # vez, o cada una devolvería el fotograma de la otra.
        self._lock = threading.Lock()

    def render(
        self, text: str, style: CaptionStyle, background: str | None, topic: str, fmt: Format = VERTICAL,
    ) -> bytes:
        with self._lock:
            try:
                return self._compose(text, style, background, topic, fmt)
            finally:
                # El motor queda en vertical, como lo carga el contenedor.
                apply_format(self._gen, VERTICAL)

    def _compose(
        self, text: str, style: CaptionStyle, background: str | None, topic: str, fmt: Format,
    ) -> bytes:
        import numpy as np
        from PIL import Image

        gen = self._gen
        apply_style(gen, style)
        apply_format(gen, fmt)
        self._previews.mkdir(parents=True, exist_ok=True)

        bg_path = self._backgrounds / background if background else None
        if bg_path is not None and not bg_path.is_file():
            bg_path = None

        clip = gen.build_background(bg_path, topic, 3.0)
        pixels = np.asarray(clip.get_frame(1.0))
        frame = Image.fromarray(pixels).convert("RGBA")
        try:
            clip.close()
        except Exception:  # noqa: BLE001 - moviepy no siempre cierra limpio
            pass

        font = gen.resolve_font(None)
        box_w = int(gen.WIDTH * 0.86)
        size = gen.fit_font_size(text, font, box_w)
        lines = gen.wrap_lines(text, font, size, box_w)
        while len(lines) > gen.MAX_CAPTION_LINES and size > gen.MIN_CAPTION_FONT_SIZE:
            size -= 4
            lines = gen.wrap_lines(text, font, size, box_w)

        overlay = Image.fromarray(gen.render_caption_image(lines, font, size))
        band_center = int(gen.HEIGHT * gen.CAPTION_Y_RATIO) + gen.CAPTION_BOX_H // 2
        frame.alpha_composite(
            overlay,
            ((gen.WIDTH - overlay.width) // 2, band_center - overlay.height // 2),
        )

        buffer = io.BytesIO()
        frame.convert("RGB").resize(fmt.preview_size, Image.LANCZOS).save(buffer, format="PNG")
        png = buffer.getvalue()

        # Se deja copia en disco para poder mirarla al depurar, pero lo que
        # viaja al navegador son los bytes: así una previsualización posterior
        # no puede pisar el archivo mientras la respuesta anterior aún se envía.
        (self._previews / "preview.png").write_bytes(png)
        return png
