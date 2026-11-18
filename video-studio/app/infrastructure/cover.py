"""
Pinta la portada con PIL: la imagen con más color y contraste, una sombra que
separa el texto del fondo y el título enorme, con su palabra resaltada.

Dos medidas mandan sobre el diseño:

- La cuadrícula de perfil de Instagram y TikTok enseña el centro 3:4 de una
  portada 9:16 (1080x1440 de 1080x1920): lo que quede fuera de y ∈ [240, 1680]
  se recorta. Todo el texto cae dentro, con margen.
- Se mira en miniatura, a unos 120 px de ancho. Por eso la letra es la más
  gorda que haya (la del motor, Arial Black si no hay otra), con borde o caja,
  y una sola palabra cambia de color: dos colores de acento ya no se leen.
"""

from __future__ import annotations

import hashlib
import io
import itertools
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from app.domain.background import is_image
from app.domain.cover import CoverWord

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
YELLOW = (255, 214, 10, 255)
RED = (229, 31, 47, 255)

JPEG_QUALITY = 90
#: El fotograma de un clip que hace de fondo: pasado el primer segundo, que en
#: los de stock suele ser un fundido.
CLIP_FRAME_AT = 1.0


@dataclass(frozen=True)
class Layout:
    #: Centro vertical del bloque de texto, en fracción de la altura.
    center: float
    #: Alto máximo del bloque, en fracción de la altura.
    max_height: float
    #: Sombra de arriba abajo: (desde, hasta, opacidad en «desde», en «hasta»).
    shade: tuple[float, float, float, float]


LAYOUTS: dict[str, Layout] = {
    # Impacto y Franja van al tercio de abajo: el guion visual pone las caras
    # en la mitad superior, y un título encima de una cara la tapa.
    "impacto": Layout(center=0.69, max_height=0.32, shade=(0.40, 1.0, 0.0, 0.88)),
    "franja": Layout(center=0.70, max_height=0.28, shade=(0.45, 1.0, 0.0, 0.55)),
    # Titular, arriba: para las imágenes con el motivo abajo o sin motivo.
    "titular": Layout(center=0.29, max_height=0.28, shade=(0.0, 0.62, 0.92, 0.0)),
}

MAX_FONT = 260
MIN_FONT = 64
FONT_STEP = 4
MAX_LINES = 4
BOX_WIDTH = 0.86


class PillowCoverPainter:
    def __init__(self, gen: ModuleType) -> None:
        # Del motor solo se leen la fuente y el degradado: nada de lo que
        # `apply_style` o `apply_format` sobrescriben, así que no hace falta
        # cerrojo. El tamaño llega de fuera, según el formato del video.
        self._gen = gen

    def paint(
        self,
        words: Sequence[CoverWord],
        design: str,
        background: Path | None,
        topic: str,
        size: tuple[int, int] = (1080, 1920),
        width: int | None = None,
    ) -> bytes:
        from PIL import Image

        layout = LAYOUTS.get(design, LAYOUTS["impacto"])

        frame = _punch(self._background(background, topic, size)).convert("RGBA")
        frame = _shade(frame, layout.shade)
        frame = _vignette(frame)

        text = _TextBlock(words, self._gen.resolve_font(None), size, layout, design)
        layer = text.layer()
        frame.alpha_composite(text.shadow(layer))
        frame.alpha_composite(layer)

        picture = frame.convert("RGB")
        # En pequeño: la letra está medida para el tamaño completo, así que se
        # pinta grande y se reduce al final, con el mismo encuadre.
        if width and width < size[0]:
            picture = picture.resize((width, round(size[1] * width / size[0])), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        picture.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buffer.getvalue()

    # ------------------------------------------------------------------ fondo

    def _background(self, path: Path | None, topic: str, size: tuple[int, int]):
        from PIL import Image, ImageOps

        source = None
        if path is not None and path.is_file():
            if is_image(path.name):
                try:
                    source = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
                except OSError:
                    source = None
            else:
                source = _clip_frame(path)
        if source is None:
            # El mismo degradado que pinta el motor cuando el video no tiene
            # fondo, con la misma semilla: la portada casa con su video.
            seed = int(hashlib.md5((topic or "portada").encode("utf-8")).hexdigest()[:8], 16)
            pixels = self._gen.gradient_image((seed % 1000) / 1000.0, size[0], size[1], seed)
            return Image.fromarray(pixels).convert("RGB")
        return _fit(source, size)


def _clip_frame(path: Path):
    """Un fotograma del clip a tamaño completo, o None si ffmpeg no puede."""
    from PIL import Image

    cmd = [
        "ffmpeg", "-loglevel", "error", "-ss", str(CLIP_FRAME_AT), "-i", str(path),
        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True, timeout=30).stdout
        return Image.open(io.BytesIO(out)).convert("RGB") if out else None
    except (subprocess.SubprocessError, OSError):
        return None


def _fit(image, size: tuple[int, int], zoom: float = 1.04, focus: float = 0.38):
    """
    Llena el cuadro sin deformar, un poco más cerca que el video para que el
    motivo gane presencia. Si sobra alto, recorta más de abajo que de arriba
    (`focus` < 0,5): ahí no suelen estar las caras.
    """
    from PIL import Image

    w, h = size
    scale = max(w / image.width, h / image.height) * zoom
    crop_w, crop_h = w / scale, h / scale
    left = (image.width - crop_w) / 2
    top = (image.height - crop_h) * focus
    return image.resize(size, Image.LANCZOS, box=(left, top, left + crop_w, top + crop_h))


def _punch(image):
    """Más color y más contraste: en una miniatura lo apagado se pierde."""
    from PIL import ImageEnhance

    image = ImageEnhance.Color(image).enhance(1.2)
    return ImageEnhance.Contrast(image).enhance(1.1)


def _shade(frame, shade: tuple[float, float, float, float]):
    """Oscurece una franja de arriba abajo para que el texto despegue del fondo."""
    import numpy as np
    from PIL import Image

    start, end, from_alpha, to_alpha = shade
    h = frame.height
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)
    t = np.clip((y - start) / max(end - start, 1e-6), 0.0, 1.0)
    t = t * t * (3 - 2 * t)  # smoothstep: sin borde visible donde empieza
    alpha = (from_alpha + (to_alpha - from_alpha) * t) * 255.0
    mask = Image.fromarray(alpha.astype("uint8")[:, None]).resize((frame.width, h))
    black = Image.new("RGBA", frame.size, BLACK)
    black.putalpha(mask)
    return Image.alpha_composite(frame, black)


def _vignette(frame, strength: float = 0.38):
    """Esquinas más oscuras: lleva el ojo al centro, donde están el motivo y el título."""
    import numpy as np
    from PIL import Image

    w, h = frame.size
    yy, xx = np.mgrid[0:h:4, 0:w:4].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    alpha = np.clip((d - 0.55) / 0.9, 0.0, 1.0) * strength * 255.0
    mask = Image.fromarray(alpha.astype("uint8")).resize((w, h), Image.BILINEAR)
    black = Image.new("RGBA", frame.size, BLACK)
    black.putalpha(mask)
    return Image.alpha_composite(frame, black)


# ---------------------------------------------------------------------- texto

class _TextBlock:
    """El título colocado: tamaño, líneas y dónde va cada palabra."""

    def __init__(
        self,
        words: Sequence[CoverWord],
        font_path: str,
        size: tuple[int, int],
        layout: Layout,
        design: str,
    ) -> None:
        from PIL import ImageFont

        self._words = list(words) or [CoverWord("SIN TÍTULO", False)]
        self._font_path = font_path
        self._size = size
        self._layout = layout
        self._design = design

        box_w = size[0] * BOX_WIDTH
        max_h = size[1] * layout.max_height
        for font_size in range(MAX_FONT, MIN_FONT - 1, -FONT_STEP):
            font = ImageFont.truetype(font_path, font_size)
            lines = self._wrap(font, box_w)
            if lines and self._height(font, len(lines)) <= max_h:
                break
        else:
            font = ImageFont.truetype(font_path, MIN_FONT)
            lines = self._wrap(font, box_w) or [list(range(len(self._words)))]
        self._font = font
        self._lines = lines

    # Medidas ----------------------------------------------------------------

    def _stroke(self, font) -> int:
        return round(font.size * 0.085) if self._design == "impacto" else round(font.size * 0.04)

    def _pad(self, font) -> tuple[int, int]:
        """Holgura de la franja o la caja alrededor del texto."""
        return round(font.size * 0.22), round(font.size * 0.14)

    def _width(self, font, text: str) -> float:
        extra = 2 * self._stroke(font)
        if self._design == "franja":
            extra += 2 * self._pad(font)[0]
        return font.getlength(text) + extra

    def _cap(self, font) -> int:
        top, bottom = font.getbbox("H")[1], font.getbbox("H")[3]
        return bottom - top

    def _gap(self, font) -> int:
        # Las franjas y las cajas necesitan aire entre líneas; las tildes de
        # las mayúsculas (Á, É, Ñ) también.
        factor = 0.62 if self._design in ("franja", "titular") else 0.36
        return round(self._cap(font) * factor)

    def _height(self, font, lines: int) -> int:
        return lines * self._cap(font) + (lines - 1) * self._gap(font)

    def _wrap(self, font, box_w: float) -> list[list[int]]:
        """
        Las líneas como índices de palabras, lo más parejas posible: un reparto
        a lo bruto deja huérfana la última palabra («…QUE NADIE TE / CUENTA»).
        Con doce palabras y cuatro líneas como mucho, probar todos los cortes
        cuesta nada. Lista vacía si no cabe.
        """
        texts = [w.text for w in self._words]
        if any(self._width(font, t) > box_w for t in texts):
            return []
        n = len(texts)
        for count in range(1, min(MAX_LINES, n) + 1):
            best: tuple[float, list[list[int]]] | None = None
            for cuts in itertools.combinations(range(1, n), count - 1):
                bounds = (0, *cuts, n)
                lines = [list(range(a, b)) for a, b in itertools.pairwise(bounds)]
                widest = max(self._width(font, " ".join(texts[i] for i in line)) for line in lines)
                if widest <= box_w and (best is None or widest < best[0]):
                    best = (widest, lines)
            if best is not None:
                return best[1]
        return []

    # Dibujo -----------------------------------------------------------------

    def layer(self):
        from PIL import Image, ImageDraw

        w, h = self._size
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        font = self._font
        cap, gap = self._cap(font), self._gap(font)
        stroke = self._stroke(font)
        pad_x, pad_y = self._pad(font)
        space = font.getlength(" ")

        top = h * self._layout.center - self._height(font, len(self._lines)) / 2
        for row, line in enumerate(self._lines):
            baseline = top + cap + row * (cap + gap)
            words = [self._words[i] for i in line]
            widths = [font.getlength(word.text) for word in words]
            total = sum(widths) + space * (len(words) - 1)
            x = w / 2 - total / 2

            if self._design == "franja":
                draw.rectangle(
                    (x - pad_x, baseline - cap - pad_y, x + total + pad_x, baseline + pad_y), fill=YELLOW,
                )

            for word, width in zip(words, widths):
                fill, outline = self._colors(word)
                if self._design == "titular" and word.highlighted:
                    draw.rounded_rectangle(
                        (x - pad_x * 0.6, baseline - cap - pad_y, x + width + pad_x * 0.6, baseline + pad_y),
                        radius=round(font.size * 0.12), fill=RED,
                    )
                    outline = None
                draw.text(
                    (x, baseline), word.text, font=font, fill=fill, anchor="ls",
                    stroke_width=stroke if outline else 0, stroke_fill=outline,
                )
                x += width + space

        if self._design == "franja":
            # Inclinada como un rótulo pegado encima: rompe la cuadrícula del fondo.
            layer = layer.rotate(2.5, resample=Image.BICUBIC, center=(w / 2, h * self._layout.center))
        return layer

    def shadow(self, layer):
        """La misma silueta en negro, difuminada y algo más abajo: despega el texto del fondo."""
        from PIL import Image, ImageFilter

        shifted = Image.new("L", self._size, 0)
        shifted.paste(layer.getchannel("A"), (0, round(self._font.size * 0.05)))
        alpha = shifted.filter(ImageFilter.GaussianBlur(self._font.size * 0.07))
        shadow = Image.new("RGBA", self._size, BLACK)
        shadow.putalpha(alpha.point(lambda v: int(v * 0.8)))
        return shadow

    def _colors(self, word: CoverWord) -> tuple[tuple, tuple | None]:
        """Relleno y borde de cada palabra según el diseño."""
        if self._design == "franja":
            return (RED if word.highlighted else BLACK), None
        if self._design == "titular":
            return WHITE, BLACK
        return (YELLOW if word.highlighted else WHITE), BLACK
