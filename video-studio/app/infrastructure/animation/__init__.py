"""Puerto `Animator`: elige el adaptador según el proveedor de `domain.animation`."""

from __future__ import annotations

from collections.abc import Mapping

from app.domain.animation import GeneratedClip, VideoProvider
from app.domain.errors import AnimatorError
from app.domain.illustration import GeneratedImage
from app.infrastructure.animation import gemini_omni

#: Tope de espera de la petición que genera el clip. Un video tarda minutos; el
#: plantón de la interfaz para animaciones (ANIMATION_GIVE_UP_MS en
#: web/application/use-cases/animate-scenes.ts) tiene que quedar por encima,
#: contando la cola, para que el usuario vea el motivo real y no «sin respuesta».
HTTP_TIMEOUT = 600


class HttpAnimator:
    def __init__(self, timeout: int = HTTP_TIMEOUT) -> None:
        self._timeout = timeout

    def animate(
        self,
        provider: VideoProvider,
        model: str,
        credentials: Mapping[str, str | None],
        image: GeneratedImage,
        prompt: str,
        seconds: int,
        aspect: str = "9:16",
    ) -> GeneratedClip:
        if provider.id == "google":
            return gemini_omni.animate(
                credentials.get(provider.key_env), model, image, prompt, seconds, provider.resolution, self._timeout,
                aspect=aspect,
            )
        raise AnimatorError(f"No hay adaptador para {provider.name}.")
