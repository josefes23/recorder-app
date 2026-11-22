"""
Nano Banana por la API nativa de Gemini (`generateContent`).

La guía de AI Studio documenta además la API de Interactions, pero no enseña
su respuesta y con una clave del nivel gratuito no se puede ver: los modelos de
imagen tienen cupo cero ahí. `generateContent` es la vía estable que estos
modelos anuncian en el catálogo (`supportedGenerationMethods`) y su respuesta
está documentada desde hace tiempo.

Las imágenes de referencia van detrás del texto como partes `inline_data`, en
orden: es como la guía de Gemini enseña a editar una imagen o a combinar
varias. Sin probar contra la API (sin facturación no hay cupo de imagen).
"""

from __future__ import annotations

import base64
from collections.abc import Sequence

import requests

from app.domain.errors import IllustratorError
from app.domain.illustration import GeneratedImage
from app.infrastructure.google_quota import KEYS_PAGE, read_quota
from app.infrastructure.imaging import compact, shrink, sniff_extension

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

#: Resolución que se pide. 2K deja margen al zoom del motor sobre 1080x1920;
#: Lite no documenta 2K, así que va a 1K.
IMAGE_SIZE = {"gemini-3.1-flash-lite-image": "1K"}
DEFAULT_SIZE = "2K"

FREE_TIER = (
    "Google trata tu clave de Gemini como del nivel gratuito, y ahí «{model}» tiene cupo "
    "cero{detail}. Si tienes créditos o facturación, la clave tiene que ser de ese proyecto: "
    f"mira el plan de cada clave en {KEYS_PAGE}. O usa Cloudflare, que es gratis."
)


#: Lado mayor de cada referencia. Más que en Cloudflare: al corregir, la
#: referencia es la imagen entera que se edita, y aquí no se paga por teselas.
REFERENCE_SIDE = 1536
MAX_REFERENCES = 4


def paint(
    api_key: str | None,
    model: str,
    prompt: str,
    timeout: int,
    references: Sequence[GeneratedImage] = (),
    aspect: str = "9:16",
) -> GeneratedImage:
    parts: list[dict] = [{"text": prompt}]
    for reference in references[:MAX_REFERENCES]:
        data = shrink(reference.data, REFERENCE_SIDE)
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode("ascii")}})
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect, "imageSize": IMAGE_SIZE.get(model, DEFAULT_SIZE)},
        },
    }
    try:
        response = requests.post(
            URL.format(model=model),
            headers={"x-goog-api-key": api_key or "", "Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )
    except requests.Timeout:
        raise IllustratorError(f"Google tardó más de {timeout} segundos en pintar la escena. Vuelve a intentarlo.") from None
    except requests.RequestException:
        raise IllustratorError("Sin conexión con la API de Google.") from None

    raise_for_status(response, model)
    return extract_image(response.json())


def raise_for_status(response: requests.Response, model: str) -> None:
    if response.ok:
        return
    body = compact(response.text, 400)
    lowered = body.lower()
    # Google contesta 400 a una clave inválida en vez de 401.
    if response.status_code in (401, 403) or (response.status_code == 400 and "api key" in lowered):
        raise IllustratorError("La clave de Gemini no es válida o no tiene permiso para generar imágenes.")
    if response.status_code == 404:
        raise IllustratorError(f"Google no sirve el modelo «{model}». Elige otro en «Generador de imágenes».")
    if response.status_code == 429:
        quota = read_quota(response)
        detail = quota.detail()
        if quota.free_tier and quota.zero:
            raise IllustratorError(FREE_TIER.format(model=model, detail=detail))
        if quota.free_tier:
            raise IllustratorError(
                f"Se acabó el cupo gratuito de Gemini{detail}. Espera o activa la facturación "
                f"de la clave ({KEYS_PAGE})."
            )
        if quota.zero:
            raise IllustratorError(
                f"Tu plan de Google no tiene cupo para «{model}»{detail}. "
                "Elige otro modelo en «Generador de imágenes»."
            )
        raise IllustratorError(
            f"Google frenó la petición: límite por minuto o saturación de su lado{detail}. "
            "Prueba en un momento."
        )
    raise IllustratorError(f"La API de Google devolvió {response.status_code}: {body[:200]}")


def extract_image(data: dict) -> GeneratedImage:
    """
    La última imagen de la respuesta que no sea un borrador. Los modelos que
    razonan pueden mandar imágenes intermedias marcadas con `thought`; la
    buena es la final.
    """
    blocked = (data.get("promptFeedback") or {}).get("blockReason")
    if blocked:
        raise IllustratorError(
            f"Google rechazó la descripción ({blocked}). Cámbiala y vuelve a intentarlo."
        )

    candidates = data.get("candidates") or []
    found: tuple[str, str | None] | None = None
    for candidate in candidates:
        for part in (candidate.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data") or {}
            if inline.get("data") and not part.get("thought"):
                found = (inline["data"], inline.get("mimeType") or inline.get("mime_type"))

    if found is None:
        reason = candidates[0].get("finishReason") if candidates else None
        detail = f" ({reason})" if reason and reason != "STOP" else ""
        raise IllustratorError(
            f"Google no devolvió ninguna imagen{detail}. Cambia la descripción y vuelve a intentarlo."
        )

    raw = base64.b64decode(found[0])
    return GeneratedImage(raw, sniff_extension(raw, found[1]))
