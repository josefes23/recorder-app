"""Puerto `Illustrator`: elige el adaptador según el generador de `domain.illustration`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.domain.errors import IllustratorError
from app.domain.illustration import GeneratedImage, ImageProvider
from app.infrastructure.imaging import cloudflare, gemini

# Tope de espera por imagen. Tiene que quedar POR DEBAJO del plantón de la
# interfaz (GIVE_UP_MS en job-tracker.ts, cinco minutos), contando con que la
# imagen puede esperar turno detrás de otras: si no, el usuario ve «el
# servidor no contesta» en vez del motivo real.
HTTP_TIMEOUT = 120


class HttpIllustrator:
    def __init__(self, timeout: int = HTTP_TIMEOUT) -> None:
        self._timeout = timeout

    def illustrate(
        self,
        provider: ImageProvider,
        model: str,
        credentials: Mapping[str, str | None],
        prompt: str,
        seed: int | None = None,
        references: Sequence[GeneratedImage] = (),
    ) -> GeneratedImage:
        if provider.id == "google":
            # Gemini no documenta semilla para imágenes. Las referencias sí
            # viajan —sin ellas no se podría corregir una imagen—, aunque con
            # Nano Banana no están probadas (sin facturación no hay cupo).
            return gemini.paint(credentials.get("GEMINI_API_KEY"), model, prompt, self._timeout, references)
        if provider.id == "cloudflare":
            return cloudflare.paint(
                credentials.get("CLOUDFLARE_ACCOUNT_ID"),
                credentials.get("CLOUDFLARE_API_TOKEN"),
                model,
                prompt,
                self._timeout,
                seed,
                references,
            )
        raise IllustratorError(f"No hay adaptador para {provider.name}.")
