"""Petición de chat compatible con OpenAI: la comparten NVIDIA, Google y DeepSeek."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.errors import WriterError


@dataclass(frozen=True)
class Endpoint:
    #: Nombre corto para los mensajes de error.
    who: str
    chat_url: str
    catalog_url: str
    #: Modelos del catálogo que no sirven para redactar.
    exclude: re.Pattern[str] | None = None
    #: El catálogo se puede consultar sin clave.
    public_catalog: bool = False


def chat(endpoint: Endpoint, api_key: str | None, model: str, system: str, prompt: str, timeout: int) -> str:
    import requests

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        # Holgado a propósito. Los modelos que razonan gastan el presupuesto en
        # pensar antes de escribir —medido con Gemini 3.6 Flash: 980 tokens de
        # razonamiento y solo 40 para el guion— y con el límite justo la
        # respuesta salía cortada a mitad de frase.
        "max_tokens": 4096,
        "temperature": 0.7,
        "top_p": 0.9,
        "stream": False,
    }
    try:
        response = requests.post(
            endpoint.chat_url,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except requests.Timeout:
        # Medido en NVIDIA: el tamaño del modelo casi no influye —un 3B tardó lo
        # mismo que un 70B—, así que manda la cola del proveedor. Sugerir uno
        # más pequeño no arreglaría nada.
        raise WriterError(
            f"{endpoint.who} tardó más de {timeout // 60} minutos. Vuelve a intentarlo, "
            "o cambia de proveedor en «Modelo del guion»."
        ) from None
    except requests.RequestException:
        raise WriterError(f"Sin conexión con la API de {endpoint.who}.") from None

    # El cuerpo de error llega con saltos de línea y sangría; en la interfaz es
    # una línea de texto, así que se compacta antes de enseñarlo.
    body = " ".join(response.text.split())
    who = endpoint.who

    # Google contesta 400 a una clave inválida en vez de 401, así que no basta
    # con mirar el código.
    if response.status_code in (401, 403) or (
        response.status_code == 400 and "api key" in body.lower()
    ):
        raise WriterError(f"La API key de {who} no es válida.")
    if response.status_code == 402:
        raise WriterError(f"La cuenta de {who} no tiene saldo.")
    if response.status_code == 404:
        raise WriterError(f"{who} no sirve el modelo «{model}». Elige otro en «Modelo del guion».")
    if response.status_code == 429:
        raise WriterError("Límite de peticiones alcanzado. Prueba en un momento.")
    if not response.ok:
        raise WriterError(f"La API de {who} devolvió {response.status_code}: {body[:200]}")

    choices = response.json().get("choices") or []
    if not choices:
        raise WriterError(f"La respuesta de {who} llegó vacía. Vuelve a intentarlo.")

    # Un guion cortado a mitad de frase no es un guion: mejor decirlo que
    # colarlo como bueno.
    if choices[0].get("finish_reason") == "length":
        raise WriterError(
            f"{who} cortó el guion por longitud. Prueba otra vez, o elige otro "
            "modelo en «Modelo del guion»."
        )

    return choices[0].get("message", {}).get("content") or ""


def catalog(endpoint: Endpoint, api_key: str | None, timeout: int = 10) -> list[str] | None:
    """Identificadores del catálogo vivo, ya filtrados. None si no se pudo consultar."""
    if not endpoint.public_catalog and not api_key:
        return None

    import requests

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = requests.get(endpoint.catalog_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        # Google devuelve los identificadores con prefijo «models/».
        ids = sorted(m["id"].removeprefix("models/") for m in response.json().get("data", []))
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None

    if endpoint.exclude is not None:
        ids = [i for i in ids if not endpoint.exclude.search(i)]
    return ids or None
