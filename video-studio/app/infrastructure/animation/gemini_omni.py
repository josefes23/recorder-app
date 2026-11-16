"""
Gemini Omni Flash por la API de Interactions: de una imagen, un clip de video.

Sigue la guía de AI Studio (aistudio.google.com/docs/omni, leída el
16-11-2026):

- `POST /v1beta/interactions` con la imagen en línea (base64) y el texto, la
  tarea `image_to_video` y `response_format` con relación de aspecto,
  resolución y duración («3s» a «15s»).
- Se pide `delivery: "uri"`: un clip de más de 4 MB no cabe en la respuesta.
  La URI se consulta en `/v1beta/files/{id}` hasta que está `ACTIVE` y se baja
  con `:download?alt=media`.

Sin probar contra la API: Omni no tiene nivel gratuito y no hay clave con
facturación a mano. Los nombres de campos son los de la guía; si Google los
cambia, el error de la API llega tal cual a la interfaz.
"""

from __future__ import annotations

import base64
import re
import time
from collections.abc import Callable

import requests

from app.domain.animation import ASPECT_RATIO, GeneratedClip
from app.domain.errors import AnimatorError
from app.domain.illustration import GeneratedImage
from app.infrastructure.imaging import compact, shrink

BASE = "https://generativelanguage.googleapis.com/v1beta"
INTERACTIONS = f"{BASE}/interactions"
FILE = BASE + "/files/{id}"
DOWNLOAD = BASE + "/files/{id}:download?alt=media"

#: Lado mayor de la imagen que viaja. El clip sale a 720x1280: más no aporta.
IMAGE_SIDE = 1280

#: Cada cuánto se pregunta si el archivo ya está listo, y hasta cuándo.
POLL_SECONDS = 5
POLL_LIMIT = 600

#: Bajar un clip de unos MB ya listo.
DOWNLOAD_TIMEOUT = 120

NO_FREE_TIER = (
    "Gemini Omni no tiene nivel gratuito: activa la facturación de tu clave de Google "
    "en ai.dev/rate-limit para poder animar escenas."
)


def request_body(
    model: str, image: GeneratedImage, prompt: str, seconds: int, resolution: str, aspect: str = ASPECT_RATIO
) -> dict:
    data = shrink(image.data, IMAGE_SIDE)  # siempre JPEG
    return {
        "model": model,
        "input": [
            {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mime_type": "image/jpeg"},
            {"type": "text", "text": prompt},
        ],
        "response_format": {
            "type": "video",
            "aspect_ratio": aspect,
            "resolution": resolution,
            "duration": f"{seconds}s",
            "delivery": "uri",
        },
        # Una sola imagen y que sea el primer fotograma: la tarea lo fija. Sin
        # ella el modelo puede tomarla como simple referencia de estilo.
        "generation_config": {"video_config": {"task": "image_to_video"}},
    }


def animate(
    api_key: str | None,
    model: str,
    image: GeneratedImage,
    prompt: str,
    seconds: int,
    resolution: str,
    timeout: int,
    sleep: Callable[[float], None] = time.sleep,
    aspect: str = ASPECT_RATIO,
) -> GeneratedClip:
    headers = {"x-goog-api-key": api_key or ""}
    try:
        response = requests.post(
            INTERACTIONS,
            headers={**headers, "Content-Type": "application/json"},
            json=request_body(model, image, prompt, seconds, resolution, aspect),
            timeout=timeout,
        )
    except requests.Timeout:
        raise AnimatorError(f"Google tardó más de {timeout // 60} minutos en animar la escena. Vuelve a intentarlo.") from None
    except requests.RequestException:
        raise AnimatorError("Sin conexión con la API de Google.") from None

    raise_for_status(response, model)
    inline, uri = extract_video(response.json())
    if inline is not None:
        return GeneratedClip(inline)
    return GeneratedClip(download(uri or "", headers, sleep))


def raise_for_status(response: requests.Response, model: str) -> None:
    if response.ok:
        return
    body = compact(response.text, 400)
    lowered = body.lower()
    # Google contesta 400 a una clave inválida en vez de 401.
    if response.status_code in (401, 403) or (response.status_code == 400 and "api key" in lowered):
        raise AnimatorError("La clave de Gemini no es válida o no tiene permiso para generar video.")
    if response.status_code == 404:
        raise AnimatorError(f"Google no sirve el modelo de video «{model}». Revisa GEMINI_VIDEO_MODEL en el .env.")
    if response.status_code == 429:
        if "free tier" in lowered or "limit: 0" in lowered or "billing" in lowered:
            raise AnimatorError(NO_FREE_TIER)
        raise AnimatorError("Límite de peticiones de Gemini alcanzado. Prueba en un momento.")
    if response.status_code == 400 and ("safety" in lowered or "blocked" in lowered or "policy" in lowered):
        raise AnimatorError("Google rechazó la imagen o la descripción por sus filtros. Prueba con otra.")
    raise AnimatorError(f"La API de Google devolvió {response.status_code}: {body[:200]}")


def extract_video(data: dict) -> tuple[bytes | None, str | None]:
    """
    El video de la respuesta: sus bytes si vinieron en línea, o su URI. La guía
    lo enseña dentro de `steps` (el paso `model_output`); el `output_video` de
    arriba es del SDK, pero se mira primero por si la API REST también lo trae.
    """
    candidates: list[dict] = []
    if isinstance(data.get("output_video"), dict):
        candidates.append(data["output_video"])
    for step in reversed(data.get("steps") or []):
        if step.get("type") != "model_output":
            continue
        candidates += [c for c in step.get("content") or [] if c.get("type") == "video"]

    for video in candidates:
        if video.get("data"):
            return base64.b64decode(video["data"]), None
        if video.get("uri"):
            return None, video["uri"]

    status = data.get("status")
    detail = f" (estado: {status})" if status and status != "completed" else ""
    raise AnimatorError(
        f"Google no devolvió ningún video{detail}. Puede que la imagen o la descripción no "
        "pasaran sus filtros: prueba con otra."
    )


_FILE_ID = re.compile(r"files/([^:/?]+)")


def file_id(uri: str) -> str:
    match = _FILE_ID.search(uri)
    if not match:
        raise AnimatorError(f"Google devolvió una dirección de video que no se entiende: {uri[:120]}")
    return match.group(1)


def download(uri: str, headers: dict, sleep: Callable[[float], None] = time.sleep) -> bytes:
    """Espera a que el archivo esté `ACTIVE` y lo baja."""
    fid = file_id(uri)
    waited = 0
    while True:
        try:
            state = requests.get(FILE.format(id=fid), headers=headers, timeout=60)
        except requests.RequestException:
            raise AnimatorError("Se cortó la conexión con Google mientras se preparaba el video.") from None
        if not state.ok:
            raise AnimatorError(f"Google no encuentra el video generado ({state.status_code}). Vuelve a intentarlo.")
        current = (state.json() or {}).get("state")
        if current == "ACTIVE":
            break
        if current == "FAILED":
            raise AnimatorError("Google no pudo terminar el video. Vuelve a intentarlo.")
        if waited >= POLL_LIMIT:
            raise AnimatorError(f"El video no estuvo listo en {POLL_LIMIT // 60} minutos. Vuelve a intentarlo.")
        sleep(POLL_SECONDS)
        waited += POLL_SECONDS

    try:
        video = requests.get(DOWNLOAD.format(id=fid), headers=headers, timeout=DOWNLOAD_TIMEOUT)
    except requests.RequestException:
        raise AnimatorError("Se cortó la conexión con Google al bajar el video.") from None
    if not video.ok or not video.content:
        raise AnimatorError(f"No se pudo bajar el video de Google ({video.status_code}).")
    return video.content
