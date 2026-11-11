"""
Quién redacta el guion: los proveedores que se admiten y lo que se les pide.

Aquí viven las reglas —qué modelo por defecto, cómo se arma el encargo, cuándo
una respuesta no vale como guion— pero no cómo se habla con cada API: eso es de
`infrastructure.llm`. Añadir un proveedor es añadir una entrada a PROVIDERS y
enseñarle al compositor a llamarlo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.errors import WriterError
from app.domain.script import clean_script

# Variable de entorno que guarda el proveedor elegido en la interfaz.
PROVIDER_SETTING = "SCRIPT_PROVIDER"

# Suelo por debajo del cual la respuesta no vale como guion. El objetivo son 85
# a 120 palabras; esto solo caza lo que llega roto.
MIN_WORDS = 50

SYSTEM_PROMPT = """Escribes guiones para Reels y Shorts verticales en español.

Reglas que no puedes saltarte:
- Entre 85 y 120 palabras. Es el rango que produce entre 30 y 45 segundos de voz.
- Español natural y hablado. El texto se va a ESCUCHAR, no a leer: frases cortas,
  sin subordinadas largas, sin viñetas, sin markdown, sin emojis.
- Nada de cifras en dígitos: escribe "treinta por ciento", no "30%". El sintetizador
  de voz las pronuncia peor y descuadra la sincronía de los subtítulos.
- Puntuación cuidada. Los cortes de subtítulo se calculan a partir de las comas,
  los puntos y las interrogaciones, así que un texto mal puntuado se lee fatal.
- Estructura: gancho en los tres primeros segundos, luego dos o tres ideas
  concretas, y cierre con una llamada a la acción.

Devuelve únicamente el texto del guion. Sin título, sin comillas, sin explicaciones,
sin acotaciones de escena."""


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    note: str
    #: Variable del .env donde se guarda la clave.
    key_env: str
    #: Variable del .env donde se guarda el modelo elegido.
    model_env: str
    default_model: str
    #: Acepta imágenes con cualquiera de sus modelos: puede revisar las escenas
    #: pintadas (`domain.review`). En NVIDIA depende del modelo y DeepSeek no ve.
    sees_images: bool = False


PROVIDERS: tuple[Provider, ...] = (
    Provider(
        "nvidia", "NVIDIA NIM", "gratis · build.nvidia.com",
        "NVIDIA_API_KEY", "NVIDIA_MODEL", "meta/llama-3.3-70b-instruct",
    ),
    Provider(
        "google", "Google Gemini", "nivel gratuito con límites",
        "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-3.6-flash", sees_images=True,
    ),
    Provider(
        "deepseek", "DeepSeek", "de pago por uso",
        "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "deepseek-v4-flash",
    ),
    Provider(
        "anthropic", "Anthropic (Claude)", "de pago por uso",
        "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "claude-opus-5-5", sees_images=True,
    ),
)

_BY_ID = {p.id: p for p in PROVIDERS}


def provider_by_id(provider_id: str | None) -> Provider | None:
    return _BY_ID.get((provider_id or "").strip().lower())


def build_prompt(topic: str, notes: str = "") -> str:
    prompt = f"Tema: {topic}"
    if notes.strip():
        prompt += f"\n\nIndicaciones adicionales:\n{notes.strip()}"
    return prompt


def strip_reasoning(raw: str | None) -> str:
    """Varios modelos abiertos escupen su razonamiento en <think>…</think>."""
    return re.sub(r"<think>.*?</think>", " ", raw or "", flags=re.DOTALL | re.IGNORECASE)


def validate_script(raw: str | None) -> str:
    """Limpia la respuesta del modelo y la rechaza si no vale como guion."""
    text = clean_script(strip_reasoning(raw))
    if not text:
        raise WriterError("La respuesta llegó vacía. Vuelve a intentarlo.")

    # El sistema pide entre 85 y 120 palabras. Muy por debajo de eso no es un
    # guion corto: es uno roto. Visto con Gemini, que a veces devuelve el texto
    # cortado a mitad de palabra declarando que terminó bien, así que mirar el
    # `finish_reason` no basta.
    words = len(text.split())
    if words < MIN_WORDS:
        raise WriterError(
            f"El guion llegó incompleto ({words} palabras). "
            "Vuelve a intentarlo, o cambia de modelo en «Modelo del guion»."
        )
    return text


def short_label(provider: Provider, model: str) -> str:
    """Nombre corto para la interfaz: qué modelo va a escribir el guion."""
    if provider.id == "anthropic":
        return "Claude"
    # El identificador trae el fabricante por delante; con la cola basta.
    return f"{provider.name.split()[0]} · {model.split('/')[-1]}"


def mask_key(value: str | None) -> str | None:
    """Los últimos caracteres de una clave, para confirmar cuál está puesta."""
    return f"…{value[-4:]}" if value else None
