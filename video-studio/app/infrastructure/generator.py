"""
Puente al motor de auto-video-generator.

Ese proyecto se importa como librería y NO se modifica: el estilo se aplica
sobrescribiendo sus constantes de módulo en tiempo de ejecución, que es como el
propio generate.py las lee (dentro de las funciones, no en el import).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

from app.domain.style import CaptionStyle


def load_generator(generator_root: Path) -> ModuleType:
    """Importa auto-video-generator/scripts/generate.py como módulo."""
    scripts_dir = generator_root / "scripts"
    if not (scripts_dir / "generate.py").is_file():
        raise RuntimeError(
            f"No encuentro el motor en {scripts_dir}. video-studio depende de "
            f"auto-video-generator: deben estar en la misma carpeta padre."
        )
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("generate")


def apply_style(gen: ModuleType, style: CaptionStyle) -> None:
    """Vuelca el estilo de la interfaz sobre las constantes del motor.

    Son globales del proceso: quien lo llame debe garantizar que no hay otro
    render o previsualización componiendo a la vez.
    """
    gen.CAPTION_FONT_SIZE = style.font_size
    gen.CAPTION_STROKE = style.stroke
    gen.CAPTION_Y_RATIO = style.y_ratio
    gen.MAX_CHARS_PER_CAPTION = style.max_chars
    gen.MAX_WORDS_PER_CAPTION = style.max_words
    gen.MAX_CAPTION_LINES = style.max_lines
    gen.MIN_CAPTION_FONT_SIZE = style.min_font_size


class GeneratorTemplate:
    """Puerto `ScriptTemplate`: la plantilla genérica del motor."""

    def __init__(self, gen: ModuleType) -> None:
        self._gen = gen

    def template(self, topic: str) -> str:
        return self._gen.build_fallback_script(topic)
