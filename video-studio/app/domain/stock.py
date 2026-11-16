"""
Clips de stock: lo que se sabe de un vídeo antes de descargarlo y qué versión
merece la pena bajar.

Aquí no hay red. `infrastructure.pexels` traduce la respuesta de la API a
estos objetos y la aplicación decide con ellos qué entra en la galería.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

#: Ancho objetivo para 9:16. Subir de ahí solo añade megas: el render recorta a
#: 1080x1920 de todos modos.
TARGET_WIDTH = 1080

#: Tope por clip. Algunos publican un 1080p con bitrate desmedido (175 MB para
#: 60 s) y no compensan.
MAX_SIZE_BYTES = 100_000_000

#: Un fondo más corto que esto se repite demasiado en pantalla.
MIN_DURATION = 8


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "bg"


def clip_name(query: str, clip_id: int) -> str:
    """«finanzas_6799744.mp4»: el mismo esquema que el script del generador,
    así que la galería agrupa lo descargado por búsqueda."""
    return f"{slugify(query)}_{clip_id}.mp4"


@dataclass(frozen=True)
class Variant:
    """Una de las codificaciones que el catálogo ofrece del mismo clip."""

    width: int
    height: int
    size: int
    link: str

    @property
    def vertical(self) -> bool:
        return self.height > self.width


def _short_side(variant: Variant) -> int:
    return min(variant.width, variant.height)


def best_variant(
    variants: list[Variant], vertical: bool = True, max_bytes: int = MAX_SIZE_BYTES
) -> Variant | None:
    """
    La versión con la orientación del video que merece la pena: la más pequeña
    cuyo lado corto llegue a 1080. Si ninguna llega, la más grande que haya.
    Las que pasan del tope de tamaño se descartan antes de elegir, salvo que no
    quede otra.
    """
    matching = [v for v in variants if v.vertical == vertical and v.width != v.height]
    if not matching:
        return None
    affordable = [v for v in matching if v.size <= max_bytes] or matching
    big_enough = [v for v in affordable if _short_side(v) >= TARGET_WIDTH]
    if big_enough:
        return min(big_enough, key=_short_side)
    return max(affordable, key=_short_side)


def best_vertical(variants: list[Variant], max_bytes: int = MAX_SIZE_BYTES) -> Variant | None:
    """La versión vertical que merece la pena (ver `best_variant`)."""
    return best_variant(variants, True, max_bytes)


def smallest_variant(variants: list[Variant], vertical: bool = True) -> Variant | None:
    """La versión más ligera con esa orientación: para reproducir una muestra en el navegador, no para bajarla."""
    matching = [v for v in variants if v.vertical == vertical and v.width != v.height]
    return min(matching, key=_short_side) if matching else None


def smallest_vertical(variants: list[Variant]) -> Variant | None:
    return smallest_variant(variants, True)


@dataclass(frozen=True)
class StockClip:
    """Un clip del catálogo, con la versión ya elegida, para verlo antes de bajarlo."""

    id: int
    #: Fotograma de muestra: con él se elige sin descargar nada.
    preview: str
    duration: int
    width: int
    height: int
    size_mb: float
    author: str
    #: Página del clip en Pexels.
    url: str
    #: La versión más ligera del clip, para verlo en movimiento antes de decidir.
    play: str = ""
    #: Descarga del archivo. No sale a la interfaz: al descargar, el servidor
    #: vuelve a resolverla por el id, para no bajar cualquier URL que le manden.
    link: str = ""
    #: Nombre que tendrá en la galería, y si ya está en ella.
    name: str = ""
    owned: bool = False

    def as_dict(self) -> dict:
        data = asdict(self)
        del data["link"]
        return data
