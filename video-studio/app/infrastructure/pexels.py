"""
Pexels como catálogo de clips verticales. Licencia Pexels: uso gratuito,
también comercial, sin atribución obligatoria.

La API pide una clave gratuita (pexels.com/api). Sin ella solo contesta a unos
pocos términos comunes de una palabra que tiene cacheados, y durante poco.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import requests

from app.domain.errors import EngineError, NotFoundError
from app.domain.stock import MIN_DURATION, StockClip, Variant, best_vertical, smallest_vertical

SEARCH_URL = "https://api.pexels.com/videos/search"
CLIP_URL = "https://api.pexels.com/videos/videos/{id}"
TIMEOUT = 30
#: Resultados por búsqueda. Son miniaturas: de aquí el usuario marca los que quiere.
PER_PAGE = 30


def parse_video(video: dict) -> StockClip | None:
    """Traduce un vídeo del catálogo. None si no tiene versión vertical en mp4."""
    variants = [
        Variant(int(f["width"]), int(f["height"]), int(f.get("size") or 0), f["link"])
        for f in video.get("video_files") or []
        if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height") and f.get("link")
    ]
    chosen = best_vertical(variants)
    if chosen is None:
        return None
    lightest = smallest_vertical(variants) or chosen
    return StockClip(
        id=int(video["id"]),
        preview=video.get("image") or "",
        duration=int(video.get("duration") or 0),
        width=chosen.width,
        height=chosen.height,
        size_mb=round(chosen.size / 1e6, 1),
        author=(video.get("user") or {}).get("name") or "",
        url=video.get("url") or "",
        play=lightest.link,
        link=chosen.link,
    )


class ClipStream:
    """
    El archivo según llega de la red, con la interfaz de lectura que espera
    `BackgroundStore.save`. Al llegar al final comprueba que está entero: una
    conexión que se corta deja la respuesta corta, no un error.
    """

    def __init__(self, response: requests.Response, clip_id: int) -> None:
        self._response = response
        self._clip_id = clip_id
        self._expected = int(response.headers.get("Content-Length") or 0)
        self._received = 0
        self._chunks: Iterator[bytes] = response.iter_content(chunk_size=1 << 16)

    def read(self, size: int = -1) -> bytes:
        try:
            chunk = next(self._chunks, b"")
        except requests.RequestException as exc:
            raise EngineError(f"Se cortó la descarga del clip {self._clip_id}: {exc}") from None
        if not chunk and self._expected and self._received != self._expected:
            raise EngineError(
                f"El clip {self._clip_id} llegó incompleto: "
                f"{self._received} de {self._expected} bytes."
            )
        self._received += len(chunk)
        return chunk

    def __enter__(self) -> ClipStream:
        return self

    def __exit__(self, *exc: object) -> None:
        self._response.close()


class PexelsLibrary:
    def __init__(self, api_key: Callable[[], str | None], timeout: int = TIMEOUT) -> None:
        # La clave se pide en cada llamada: si el usuario la añade al .env con
        # el servidor en marcha, la siguiente búsqueda ya la usa.
        self._api_key = api_key
        self._timeout = timeout

    def search(self, query: str) -> list[StockClip]:
        data = self._get(
            SEARCH_URL, {"query": query, "orientation": "portrait", "per_page": PER_PAGE},
        )
        clips = (parse_video(video) for video in data.get("videos") or [])
        return [clip for clip in clips if clip and clip.duration >= MIN_DURATION]

    def clip(self, clip_id: int) -> StockClip:
        clip = parse_video(self._get(CLIP_URL.format(id=clip_id), {}, clip_id=clip_id))
        if clip is None:
            raise EngineError(f"El clip {clip_id} no tiene versión vertical en mp4.")
        return clip

    def open(self, clip: StockClip) -> ClipStream:
        try:
            response = requests.get(clip.link, stream=True, timeout=self._timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise EngineError(f"No se pudo descargar el clip {clip.id}: {exc}") from None
        return ClipStream(response, clip.id)

    def _get(self, url: str, params: dict, clip_id: int | None = None) -> dict:
        key = self._api_key()
        try:
            response = requests.get(
                url,
                params=params,
                headers={"Authorization": key} if key else {},
                timeout=self._timeout,
            )
        except requests.RequestException:
            raise EngineError("Sin conexión con Pexels.") from None

        if response.status_code == 401:
            if key:
                raise EngineError("Pexels rechazó la API key. Revísala en pexels.com/api.")
            raise EngineError(
                "Pexels pide una API key para esta búsqueda. Consigue una gratis en "
                "pexels.com/api y guárdala como PEXELS_API_KEY en el .env del generador."
            )
        if response.status_code == 404 and clip_id is not None:
            raise NotFoundError(f"Pexels ya no tiene el clip {clip_id}.")
        if response.status_code == 429:
            raise EngineError("Límite de peticiones de Pexels alcanzado. Prueba más tarde.")
        if not response.ok:
            body = " ".join(response.text.split())[:200]
            raise EngineError(f"Pexels devolvió HTTP {response.status_code}: {body}")
        return response.json()
