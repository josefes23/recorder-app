"""
Redacción del guion con un modelo de lenguaje.

Cuatro proveedores intercambiables, según la clave que tengas en el `.env`:

  - NVIDIA NIM — gratis, pero el nivel gratuito encola: medido, entre noventa
    segundos y más de tres minutos, y el tamaño del modelo apenas influye.
  - Google Gemini — nivel gratuito con límites de uso.
  - DeepSeek — de pago por uso.
  - Anthropic (Claude) — de pago por uso.

Los tres primeros hablan el mismo protocolo compatible con OpenAI, así que
comparten cliente (`_chat`); Anthropic va por su SDK.

Cada proveedor es una entrada de `PROVIDERS` con dónde vive su clave, qué
catálogo ofrece y cómo se le pide un guion. Añadir uno nuevo es añadir una
entrada; no hay condicionales repartidos por el módulo.

Es opcional: sin credenciales la app sigue siendo usable — pegas el guion a mano
o tiras de la plantilla local del motor.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.engine import ROOT, clean_script, gen

ENV_FILE = ROOT / ".env"

# Tope de espera contra cualquier proveedor. Tiene que quedar POR DEBAJO del que
# usa la interfaz para darse por vencida (GIVE_UP_MS en job-tracker.ts, cinco
# minutos): si empatan, el usuario ve «el servidor no contesta» en lugar del
# motivo real.
HTTP_TIMEOUT = 180

# Suelo por debajo del cual la respuesta no vale como guion. El objetivo son 85
# a 120 palabras; esto solo caza lo que llega roto.
MIN_WORDS = 50

# --------------------------------------------------------------------------- #
# NVIDIA NIM
# --------------------------------------------------------------------------- #

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_CATALOG_URL = "https://integrate.api.nvidia.com/v1/models"
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"

# Modelos de chat que van bien redactando en español. Se cruzan con el catálogo
# vivo, así que si NVIDIA retira alguno simplemente deja de aparecer.
NVIDIA_RECOMMENDED = (
    "meta/llama-3.3-70b-instruct",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "mistralai/mistral-large-2-instruct",
    "writer/palmyra-creative-122b",
    "openai/gpt-oss-120b",
    "google/gemma-4-31b-it",
)

# El catálogo mezcla modelos de chat con otros que no sirven para escribir un
# guion: incrustaciones, visión, código, traducción, moderación y modelos base.
NVIDIA_EXCLUDE = re.compile(
    r"embed|bge-|nvclip|nemoretriever|rerank|reward|guard|safety|topic-control"
    r"|code|starcoder|codestral|laguna|parse"
    r"|vision|[-/]vl-|-vl$|vila|neva|kosmos|fuyu|deplot|paligemma|omni"
    r"|cosmos-reason|video-detector|diffusion|riva-translate"
    r"|calibration|llama2-|gemma-2b|recurrentgemma|mixtral-8x22b-v0\.1",
    re.IGNORECASE,
)

# --------------------------------------------------------------------------- #
# DeepSeek
# --------------------------------------------------------------------------- #

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_CATALOG_URL = "https://api.deepseek.com/models"
DEEPSEEK_MODEL = "deepseek-v4-flash"

# Respaldo si el catálogo no contesta. No se pide «thinking» en ningún caso: un
# guion de cien palabras no lo necesita y solo añadiría espera.
DEEPSEEK_FALLBACK_MODELS = (
    ("deepseek-v4-flash", "DeepSeek V4 Flash — rápido"),
    ("deepseek-v4-pro", "DeepSeek V4 Pro — más capaz"),
)

# --------------------------------------------------------------------------- #
# Google Gemini
# --------------------------------------------------------------------------- #

# Google publica una capa compatible con OpenAI además de su API nativa. Se usa
# esa: el guion es un system + un user sin streaming, justo lo que cubre, y así
# comparte cliente con NVIDIA y DeepSeek en vez de traducir a `contents`.
GOOGLE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GOOGLE_CATALOG_URL = "https://generativelanguage.googleapis.com/v1beta/openai/models"
GOOGLE_MODEL = "gemini-3.6-flash"

GOOGLE_FALLBACK_MODELS = (
    ("gemini-3.6-flash", "Gemini 3.6 Flash — rápido"),
    ("gemini-3.1-pro", "Gemini 3.1 Pro — más capaz"),
    ("gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite — el más ligero"),
)

# El catálogo mezcla generación de imagen, vídeo, voz e incrustaciones; para
# redactar solo valen los de texto.
GOOGLE_EXCLUDE = re.compile(
    r"embedding|image|imagen|veo|tts|audio|native-audio|live|aqa|vision",
    re.IGNORECASE,
)

# --------------------------------------------------------------------------- #
# Anthropic
# --------------------------------------------------------------------------- #

ANTHROPIC_MODEL = "claude-opus-5"

# Solo se usa si no hay clave con la que preguntarle el catálogo a la API.
ANTHROPIC_FALLBACK_MODELS = (
    ("claude-opus-5", "Claude Opus 5"),
    ("claude-sonnet-5", "Claude Sonnet 5"),
    ("claude-haiku-4-5", "Claude Haiku 4.5"),
)

SYSTEM = """Escribes guiones para Reels y Shorts verticales en español.

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


# --------------------------------------------------------------------------- #
# Registro de proveedores
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    note: str
    key_env: str
    model_env: str
    default_model: str
    #: Devuelve el catálogo como [{"id", "label", "group"}, …]
    catalog: Callable[[], list[dict]]
    #: Redacta: (modelo, prompt) -> texto en crudo
    compose: Callable[[str, str], str]


def _register() -> dict[str, Provider]:
    """Se construye al final del módulo, cuando ya existen las funciones."""
    return {
        p.id: p
        for p in (
            Provider(
                "nvidia", "NVIDIA NIM", "gratis · build.nvidia.com",
                "NVIDIA_API_KEY", "NVIDIA_MODEL", NVIDIA_MODEL,
                lambda: nvidia_models(),
                lambda model, prompt: _chat(NVIDIA_URL, "NVIDIA_API_KEY", "NVIDIA", model, prompt),
            ),
            Provider(
                "google", "Google Gemini", "nivel gratuito con límites",
                "GEMINI_API_KEY", "GEMINI_MODEL", GOOGLE_MODEL,
                lambda: google_models(),
                lambda model, prompt: _chat(GOOGLE_URL, "GEMINI_API_KEY", "Google", model, prompt),
            ),
            Provider(
                "deepseek", "DeepSeek", "de pago por uso",
                "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", DEEPSEEK_MODEL,
                lambda: deepseek_models(),
                lambda model, prompt: _chat(DEEPSEEK_URL, "DEEPSEEK_API_KEY", "DeepSeek", model, prompt),
            ),
            Provider(
                "anthropic", "Anthropic (Claude)", "de pago por uso",
                "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", ANTHROPIC_MODEL,
                lambda: anthropic_models(),
                lambda model, prompt: _anthropic(model, prompt),
            ),
        )
    }


# --------------------------------------------------------------------------- #
# Credenciales y elección de proveedor
# --------------------------------------------------------------------------- #

def env(name: str) -> str | None:
    """Variable de entorno, o su valor en los .env que usa el proyecto."""
    if os.environ.get(name):
        return os.environ[name]
    for env_file in (ROOT / ".env", Path.home() / ".anthropic.env"):
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition("=")
                if key.strip() == name:
                    return value.strip().strip("'\"") or None
    return None


def provider() -> str | None:
    """El proveedor activo, o None si no hay ninguna clave.

    El elegido solo manda si tiene clave; si no, se cae al primero que la
    tenga, antes que dejar el botón «Escribir» activo para que falle al
    pulsarlo.
    """
    chosen = (env("SCRIPT_PROVIDER") or "").strip().lower()
    if chosen in PROVIDERS and env(PROVIDERS[chosen].key_env):
        return chosen
    for name, spec in PROVIDERS.items():
        if env(spec.key_env):
            return name
    return None


def model(which: str | None = None) -> str:
    spec = PROVIDERS.get(which or provider() or "")
    if spec is None:
        return ""
    return env(spec.model_env) or spec.default_model


def label() -> str | None:
    """Nombre corto para la interfaz: qué modelo va a escribir el guion."""
    which = provider()
    if which is None:
        return None
    if which == "anthropic":
        return "Claude"
    # El identificador trae el fabricante por delante; con la cola basta.
    return f"{PROVIDERS[which].name.split()[0]} · {model().split('/')[-1]}"


def available() -> bool:
    return provider() is not None


def fallback(topic: str) -> str:
    """Plantilla local del motor. Genérica a propósito: es una red de seguridad."""
    return clean_script(gen.build_fallback_script(topic))


# --------------------------------------------------------------------------- #
# Ajustes desde la interfaz
# --------------------------------------------------------------------------- #

def key_hint(name: str) -> str | None:
    """Los últimos caracteres de una clave, para confirmar cuál está puesta.

    La clave entera no sale nunca del servidor.
    """
    value = env(name)
    return f"…{value[-4:]}" if value else None


def save_env(values: dict[str, str | None]) -> None:
    """Escribe en el .env respetando el resto de líneas. None borra la clave."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.is_file() else []
    pending = dict(values)

    out: list[str] = []
    for line in lines:
        name = line.partition("=")[0].strip()
        if name in pending:
            value = pending.pop(name)
            if value is not None:
                out.append(f"{name}={value}")
        else:
            out.append(line)
    out.extend(f"{name}={value}" for name, value in pending.items() if value is not None)

    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)  # guarda claves de API: que no las lea el resto del sistema

    # env() mira primero el entorno del proceso, así que sin esto el servidor
    # seguiría usando el valor con el que arrancó hasta reiniciarlo.
    for name, value in values.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def settings() -> dict:
    """Todo lo que la interfaz necesita para pintar el panel de ajustes."""
    # El formulario muestra el proveedor elegido aunque le falte la clave: es
    # justo el caso en el que el usuario abre el panel para ponérsela.
    chosen = (env("SCRIPT_PROVIDER") or "").strip().lower()
    return {
        "provider": chosen if chosen in PROVIDERS else provider() or next(iter(PROVIDERS)),
        "label": label(),
        "providers": [
            {
                "id": spec.id,
                "name": spec.name,
                "note": spec.note,
                "key_env": spec.key_env,
                "key_hint": key_hint(spec.key_env),
                "model": model(spec.id),
                "models": spec.catalog(),
            }
            for spec in PROVIDERS.values()
        ],
    }


def save_settings(which: str, api_key: str = "", chosen: str = "") -> dict:
    """Guarda proveedor, clave y modelo. Una clave vacía deja la que hubiera."""
    spec = PROVIDERS.get(which)
    if spec is None:
        raise RuntimeError(f"Proveedor desconocido: {which}")

    values: dict[str, str | None] = {"SCRIPT_PROVIDER": which}
    if api_key.strip():
        values[spec.key_env] = api_key.strip()
    if chosen.strip():
        values[spec.model_env] = chosen.strip()

    save_env(values)
    return settings()


# --------------------------------------------------------------------------- #
# Catálogos de modelos
# --------------------------------------------------------------------------- #

_catalogs: dict[str, list[dict]] = {}


def nvidia_models() -> list[dict]:
    """Catálogo vivo de NIM, filtrado a modelos de chat. Cacheado por proceso.

    El endpoint es público: se puede pintar el desplegable sin tener clave aún.
    """
    if "nvidia" in _catalogs:
        return _catalogs["nvidia"]

    import requests

    try:
        response = requests.get(NVIDIA_CATALOG_URL, timeout=10)
        response.raise_for_status()
        ids = sorted(m["id"] for m in response.json().get("data", []))
    except (requests.RequestException, ValueError, KeyError):
        # Sin catálogo la interfaz seguiría siendo usable, pero con un único
        # modelo el desplegable no tendría sentido: mejor devolver el que hay.
        return [{"id": NVIDIA_MODEL, "label": NVIDIA_MODEL, "group": "Recomendados"}]

    chat = [i for i in ids if not NVIDIA_EXCLUDE.search(i)]
    _catalogs["nvidia"] = [
        {"id": i, "label": i, "group": "Recomendados"}
        for i in NVIDIA_RECOMMENDED
        if i in chat
    ] + [
        {"id": i, "label": i, "group": "Resto del catálogo"}
        for i in chat
        if i not in NVIDIA_RECOMMENDED
    ]
    return _catalogs["nvidia"]


def _openai_catalog(
    pid: str,
    url: str,
    key_env: str,
    exclude: re.Pattern[str] | None,
    fallback: tuple[tuple[str, str], ...],
) -> list[dict]:
    """Catálogo de un endpoint compatible con OpenAI.

    Necesita clave, así que hay lista de respaldo: el desplegable tiene que
    poder pintarse antes de que el usuario pegue la suya.
    """
    if pid in _catalogs:
        return _catalogs[pid]

    key = env(key_env)
    if key:
        import requests

        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            # Google devuelve los identificadores con prefijo «models/».
            ids = sorted(m["id"].removeprefix("models/") for m in response.json().get("data", []))
            if exclude is not None:
                ids = [i for i in ids if not exclude.search(i)]
            if ids:
                _catalogs[pid] = [{"id": i, "label": i, "group": "Modelos"} for i in ids]
                return _catalogs[pid]
        except (requests.RequestException, ValueError, KeyError):
            pass  # sin catálogo vivo se sigue con la lista de respaldo

    return [{"id": i, "label": name, "group": "Modelos"} for i, name in fallback]


def deepseek_models() -> list[dict]:
    return _openai_catalog(
        "deepseek", DEEPSEEK_CATALOG_URL, "DEEPSEEK_API_KEY", None, DEEPSEEK_FALLBACK_MODELS
    )


def google_models() -> list[dict]:
    return _openai_catalog(
        "google", GOOGLE_CATALOG_URL, "GEMINI_API_KEY", GOOGLE_EXCLUDE, GOOGLE_FALLBACK_MODELS
    )


def anthropic_models() -> list[dict]:
    """Catálogo de Anthropic. Necesita clave, así que hay lista de respaldo."""
    if "anthropic" in _catalogs:
        return _catalogs["anthropic"]

    key = env("ANTHROPIC_API_KEY")
    if key:
        try:
            import anthropic

            _catalogs["anthropic"] = [
                {"id": m.id, "label": m.display_name, "group": "Modelos"}
                for m in anthropic.Anthropic(api_key=key).models.list()
            ]
            return _catalogs["anthropic"]
        except Exception:
            pass  # sin catálogo vivo se sigue con la lista de respaldo

    return [
        {"id": i, "label": name, "group": "Modelos"} for i, name in ANTHROPIC_FALLBACK_MODELS
    ]


# --------------------------------------------------------------------------- #
# Redacción
# --------------------------------------------------------------------------- #

def write(topic: str, notes: str = "") -> str:
    which = provider()
    if which is None:
        raise RuntimeError(
            "No hay clave de API configurada. Añade una en «Modelo del guion», "
            "o escribe el guion a mano en el cuadro de texto."
        )

    prompt = f"Tema: {topic}"
    if notes.strip():
        prompt += f"\n\nIndicaciones adicionales:\n{notes.strip()}"

    raw = PROVIDERS[which].compose(model(which), prompt)

    text = clean_script(_strip_reasoning(raw))
    if not text:
        raise RuntimeError("La respuesta llegó vacía. Vuelve a intentarlo.")

    # El sistema pide entre 85 y 120 palabras. Muy por debajo de eso no es un
    # guion corto: es uno roto. Visto con Gemini, que a veces devuelve el texto
    # cortado a mitad de palabra declarando que terminó bien, así que mirar el
    # `finish_reason` no basta.
    if len(text.split()) < MIN_WORDS:
        raise RuntimeError(
            f"El guion llegó incompleto ({len(text.split())} palabras). "
            "Vuelve a intentarlo, o cambia de modelo en «Modelo del guion»."
        )
    return text


def _strip_reasoning(raw: str) -> str:
    """Varios modelos abiertos escupen su razonamiento en <think>…</think>."""
    return re.sub(r"<think>.*?</think>", " ", raw or "", flags=re.DOTALL | re.IGNORECASE)


def _chat(url: str, key_env: str, who: str, model_id: str, prompt: str) -> str:
    """Petición de chat compatible con OpenAI: la comparten NVIDIA, Google y DeepSeek."""
    import requests

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM},
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
            url,
            headers={
                "Authorization": f"Bearer {env(key_env)}",
                "Accept": "application/json",
            },
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
    except requests.Timeout:
        # Medido en NVIDIA: el tamaño del modelo casi no influye —un 3B tardó lo
        # mismo que un 70B—, así que manda la cola del proveedor. Sugerir uno más
        # pequeño no arreglaría nada.
        raise RuntimeError(
            f"{who} tardó más de {HTTP_TIMEOUT // 60} minutos. Vuelve a intentarlo, "
            "o cambia de proveedor en «Modelo del guion»."
        ) from None
    except requests.RequestException:
        raise RuntimeError(f"Sin conexión con la API de {who}.") from None

    # El cuerpo de error llega con saltos de línea y sangría; en la interfaz es
    # una línea de texto, así que se compacta antes de enseñarlo.
    body = " ".join(response.text.split())

    # Google contesta 400 a una clave inválida en vez de 401, así que no basta
    # con mirar el código.
    if response.status_code in (401, 403) or (
        response.status_code == 400 and "api key" in body.lower()
    ):
        raise RuntimeError(f"La API key de {who} no es válida.")
    if response.status_code == 402:
        raise RuntimeError(f"La cuenta de {who} no tiene saldo.")
    if response.status_code == 404:
        raise RuntimeError(
            f"{who} no sirve el modelo «{model_id}». Elige otro en «Modelo del guion»."
        )
    if response.status_code == 429:
        raise RuntimeError("Límite de peticiones alcanzado. Prueba en un momento.")
    if not response.ok:
        raise RuntimeError(f"La API de {who} devolvió {response.status_code}: {body[:200]}")

    choices = response.json().get("choices") or []
    if not choices:
        raise RuntimeError(f"La respuesta de {who} llegó vacía. Vuelve a intentarlo.")

    # Un guion cortado a mitad de frase no es un guion: mejor decirlo que
    # colarlo como bueno, que es lo que pasaba antes de mirar esto.
    if choices[0].get("finish_reason") == "length":
        raise RuntimeError(
            f"{who} cortó el guion por longitud. Prueba otra vez, o elige otro "
            "modelo en «Modelo del guion»."
        )

    return choices[0].get("message", {}).get("content") or ""


def _anthropic(model_id: str, prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    try:
        response = client.messages.create(
            model=model_id,
            max_tokens=2000,
            system=SYSTEM,
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError:
        raise RuntimeError("La API key de Anthropic no es válida.") from None
    except anthropic.RateLimitError:
        raise RuntimeError("Límite de peticiones alcanzado. Prueba en un momento.") from None
    except anthropic.APIConnectionError:
        raise RuntimeError("Sin conexión con la API de Anthropic.") from None

    # En Opus 5 los clasificadores pueden declinar: llega HTTP 200 con
    # stop_reason "refusal" y content vacío, así que hay que mirarlo antes.
    if response.stop_reason == "refusal":
        raise RuntimeError(
            "Claude declinó escribir sobre este tema. Reformúlalo o escribe el guion a mano."
        )

    return "".join(b.text for b in response.content if b.type == "text")


PROVIDERS: dict[str, Provider] = _register()
