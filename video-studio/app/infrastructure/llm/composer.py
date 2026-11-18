"""
Puerto `ScriptComposer`: sabe cómo se llama a cada proveedor de `domain.writer`.

Cuatro proveedores intercambiables:

  - NVIDIA NIM — gratis, pero el nivel gratuito encola: medido, entre noventa
    segundos y más de tres minutos, y el tamaño del modelo apenas influye.
  - Google Gemini — nivel gratuito con límites de uso.
  - DeepSeek — de pago por uso.
  - Anthropic (Claude) — de pago por uso.

Los tres primeros hablan el mismo protocolo compatible con OpenAI y comparten
cliente; Anthropic va por su SDK.
"""

from __future__ import annotations

import re

from app.domain.illustration import GeneratedImage
from app.domain.writer import Provider
from app.infrastructure.llm import anthropic_client, openai_compatible
from app.infrastructure.llm.openai_compatible import Endpoint

# Tope de espera contra cualquier proveedor. Tiene que quedar POR DEBAJO del que
# usa la interfaz para darse por vencida (GIVE_UP_MS en job-tracker.ts, cinco
# minutos): si empatan, el usuario ve «el servidor no contesta» en lugar del
# motivo real.
HTTP_TIMEOUT = 180

# --------------------------------------------------------------------------- #
# NVIDIA NIM
# --------------------------------------------------------------------------- #

NVIDIA = Endpoint(
    who="NVIDIA",
    chat_url="https://integrate.api.nvidia.com/v1/chat/completions",
    catalog_url="https://integrate.api.nvidia.com/v1/models",
    # El catálogo mezcla modelos de chat con otros que no sirven para escribir
    # un guion: incrustaciones, visión, código, traducción, moderación y base.
    exclude=re.compile(
        r"embed|bge-|nvclip|nemoretriever|rerank|reward|guard|safety|topic-control"
        r"|code|starcoder|codestral|laguna|parse"
        r"|vision|[-/]vl-|-vl$|vila|neva|kosmos|fuyu|deplot|paligemma|omni"
        r"|cosmos-reason|video-detector|diffusion|riva-translate"
        r"|calibration|llama2-|gemma-2b|recurrentgemma|mixtral-8x22b-v0\.1",
        re.IGNORECASE,
    ),
    # El endpoint es público: se puede pintar el desplegable sin tener clave.
    public_catalog=True,
)

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

# --------------------------------------------------------------------------- #
# Google Gemini
# --------------------------------------------------------------------------- #

# Google publica una capa compatible con OpenAI además de su API nativa. Se usa
# esa: el guion es un system + un user sin streaming, justo lo que cubre.
GOOGLE = Endpoint(
    who="Google",
    chat_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    catalog_url="https://generativelanguage.googleapis.com/v1beta/openai/models",
    # El catálogo mezcla generación de imagen, vídeo, voz e incrustaciones.
    exclude=re.compile(
        r"embedding|image|imagen|veo|tts|audio|native-audio|live|aqa|vision",
        re.IGNORECASE,
    ),
)

# --------------------------------------------------------------------------- #
# DeepSeek
# --------------------------------------------------------------------------- #

DEEPSEEK = Endpoint(
    who="DeepSeek",
    chat_url="https://api.deepseek.com/chat/completions",
    catalog_url="https://api.deepseek.com/models",
)

ENDPOINTS: dict[str, Endpoint] = {"nvidia": NVIDIA, "google": GOOGLE, "deepseek": DEEPSEEK}

# Listas de respaldo si el catálogo no contesta o aún no hay clave: el
# desplegable tiene que poder pintarse antes de que el usuario pegue la suya.
# No se pide «thinking» en ningún caso: un guion de cien palabras no lo necesita.
FALLBACK_MODELS: dict[str, tuple[tuple[str, str], ...]] = {
    "deepseek": (
        ("deepseek-v4-flash", "DeepSeek V4 Flash — rápido"),
        ("deepseek-v4-pro", "DeepSeek V4 Pro — más capaz"),
    ),
    "google": (
        ("gemini-3.6-flash", "Gemini 3.6 Flash — rápido"),
        ("gemini-3.1-pro", "Gemini 3.1 Pro — más capaz"),
        ("gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite — el más ligero"),
    ),
    "anthropic": (
        ("claude-opus-5-5", "Claude Opus 5.5"),
        ("claude-sonnet-5-5", "Claude Sonnet 5.5"),
        ("claude-haiku-5-5", "Claude Haiku 5.5"),
    ),
}


class HttpScriptComposer:
    def __init__(self, timeout: int = HTTP_TIMEOUT) -> None:
        self._timeout = timeout
        # Los catálogos vivos se cachean por proceso; los de respaldo no, para
        # volver a preguntar en cuanto haya clave.
        self._catalogs: dict[str, list[dict]] = {}

    def compose(
        self,
        provider: Provider,
        model: str,
        api_key: str | None,
        system: str,
        prompt: str,
        image: GeneratedImage | None = None,
    ) -> str:
        if provider.id == "anthropic":
            return anthropic_client.compose(api_key, model, system, prompt, image, provider.max_tokens)
        return openai_compatible.chat(
            ENDPOINTS[provider.id], api_key, model, system, prompt, self._timeout, image, provider.max_tokens
        )

    def catalog(self, provider: Provider, api_key: str | None) -> list[dict]:
        if provider.id in self._catalogs:
            return self._catalogs[provider.id]
        live = self._live_catalog(provider, api_key)
        if live:
            self._catalogs[provider.id] = live
            return live
        return self._fallback(provider)

    def _live_catalog(self, provider: Provider, api_key: str | None) -> list[dict] | None:
        if provider.id == "anthropic":
            return anthropic_client.catalog(api_key)
        ids = openai_compatible.catalog(ENDPOINTS[provider.id], api_key)
        if not ids:
            return None
        if provider.id == "nvidia":
            return [
                {"id": i, "label": i, "group": "Recomendados"} for i in NVIDIA_RECOMMENDED if i in ids
            ] + [
                {"id": i, "label": i, "group": "Resto del catálogo"} for i in ids if i not in NVIDIA_RECOMMENDED
            ]
        return [{"id": i, "label": i, "group": "Modelos"} for i in ids]

    @staticmethod
    def _fallback(provider: Provider) -> list[dict]:
        if provider.id == "nvidia":
            # Con un único modelo el desplegable no tendría sentido, pero es
            # mejor que nada: devuelve el que hay.
            return [{"id": provider.default_model, "label": provider.default_model, "group": "Recomendados"}]
        return [{"id": i, "label": name, "group": "Modelos"} for i, name in FALLBACK_MODELS[provider.id]]
