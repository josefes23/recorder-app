"""
Cloudflare Workers AI: FLUX.2 [klein] sobre la API REST de la cuenta.

El nivel gratuito da 10.000 neuronas al día, que se renuevan a las 00:00 UTC.
Pide un ID de cuenta y un token de API con permiso de Workers AI.

Los modelos FLUX.2 reciben el encargo como formulario multipart, no como JSON,
y contestan con el sobre habitual de la API v4: `{"result": {"image": <base64>}}`.
Aceptan `seed`: probado contra la API, la misma semilla con el mismo encargo
repite la imagen casi exacta, y otra semilla la cambia.

Y hasta cuatro imágenes de referencia, `input_image_0` a `input_image_3`. Se
mandan reducidas (REFERENCE_SIDE): cada tesela de 512x512 de entrada cuesta
neuronas, y para reconocer una cara o una forma no hace falta más.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence

import requests

from app.domain.errors import IllustratorError
from app.domain.illustration import GeneratedImage
from app.infrastructure.imaging import compact, shrink, sniff_extension

URL = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"

#: 9:16 en múltiplos de 16, que es lo que piden los modelos de difusión. El
#: motor lo lleva a 1080x1920 con un reescalado suave; más grande gasta cupo.
WIDTH, HEIGHT = 864, 1536

#: Lado mayor de cada imagen de referencia: una vertical queda en 432x768, dos
#: teselas de entrada (unas 11 neuronas con el 4B).
REFERENCE_SIDE = 768
MAX_REFERENCES = 4

DAILY_QUOTA = (
    "Se acabó el cupo gratuito de Cloudflare por hoy (10.000 neuronas). Se renueva "
    "a las 00:00 UTC; mientras tanto puedes usar otro generador."
)


FLAGGED = (
    "Cloudflare bloqueó esta imagen con su filtro de contenido. Cambia la descripción de la "
    "escena —menos piel o agua, otro plano— y vuelve a pedirla."
)


def paint(
    account_id: str | None,
    token: str | None,
    model: str,
    prompt: str,
    timeout: int,
    seed: int | None = None,
    references: Sequence[GeneratedImage] = (),
) -> GeneratedImage:
    form = {
        "prompt": (None, prompt),
        "width": (None, str(WIDTH)),
        "height": (None, str(HEIGHT)),
    }
    if seed is not None:
        form["seed"] = (None, str(seed))
    for i, reference in enumerate(references[:MAX_REFERENCES]):
        form[f"input_image_{i}"] = (f"referencia_{i}.jpg", shrink(reference.data, REFERENCE_SIDE), "image/jpeg")
    try:
        response = requests.post(
            URL.format(account=(account_id or "").strip(), model=model),
            headers={"Authorization": f"Bearer {token or ''}"},
            files=form,
            timeout=timeout,
        )
    except requests.Timeout:
        raise IllustratorError(f"Cloudflare tardó más de {timeout} segundos en pintar la escena. Vuelve a intentarlo.") from None
    except requests.RequestException:
        raise IllustratorError("Sin conexión con Cloudflare.") from None

    raise_for_status(response, model)
    return extract_image(response)


def first_error(response: requests.Response) -> str:
    """El mensaje del sobre v4 (`errors[0]`, con su código), o el cuerpo compactado."""
    try:
        errors = response.json().get("errors") or []
        if errors and errors[0].get("message"):
            code = errors[0].get("code")
            return f"{code}: {errors[0]['message']}" if code else str(errors[0]["message"])
    except (ValueError, AttributeError):
        pass
    return compact(response.text)


def raise_for_status(response: requests.Response, model: str) -> None:
    if response.ok:
        return
    message = first_error(response)
    lowered = message.lower()
    if response.status_code in (401, 403) or "authentication" in lowered:
        # Visto con un token de R2: válido y activo en la cuenta, pero sin
        # permiso de Workers AI. Cloudflare contesta «10000: Authentication error».
        raise IllustratorError(
            f"Cloudflare rechazó el token ({message}). Tiene que tener permiso de Workers AI: "
            "créalo desde Workers AI → «Use REST API» → «Create a Workers AI API Token»."
        )
    # Visto con una escena de bautismo: 400 «AiError: Your output has been flagged».
    if "flagged" in lowered:
        raise IllustratorError(FLAGGED)
    # El cupo diario agotado se reconoce por el mensaje, no por el código.
    if "neuron" in lowered or "allocation" in lowered:
        raise IllustratorError(DAILY_QUOTA)
    if response.status_code == 429:
        raise IllustratorError("Límite de peticiones de Cloudflare alcanzado. Prueba en un momento.")
    if response.status_code == 404 or "no such model" in lowered:
        raise IllustratorError(
            f"Cloudflare no encuentra «{model}» o el ID de cuenta no es correcto. Revísalos en «Generador de imágenes»."
        )
    raise IllustratorError(f"Cloudflare devolvió {response.status_code}: {message[:200]}")


def extract_image(response: requests.Response) -> GeneratedImage:
    # Algunos modelos de Workers AI devuelven la imagen en binario, sin sobre.
    content_type = response.headers.get("Content-Type", "")
    if content_type.startswith("image/"):
        return GeneratedImage(response.content, sniff_extension(response.content, content_type))

    try:
        data = response.json()
    except ValueError:
        raise IllustratorError(f"Cloudflare devolvió algo que no es una imagen: {compact(response.text)}") from None

    result = data.get("result") if isinstance(data.get("result"), dict) else data
    encoded = result.get("image") if isinstance(result, dict) else None
    if not encoded:
        raise IllustratorError(
            f"Cloudflare no devolvió ninguna imagen: {first_error(response) or 'respuesta vacía'}. "
            "Cambia la descripción y vuelve a intentarlo."
        )
    raw = base64.b64decode(encoded)
    return GeneratedImage(raw, sniff_extension(raw))
