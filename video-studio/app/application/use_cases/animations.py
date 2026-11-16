"""
Escenas animadas: encargos de clip a partir de una imagen de la galería.

Como una imagen, un clip tarda —minutos, no segundos—, así que la petición HTTP
solo publica el encargo y el clip llega por el flujo de eventos. Al terminar
se guarda en la galería junto a su imagen: el render no distingue un clip
animado de uno de Pexels. La imagen original no se toca, así que siempre se
puede volver a ella o animarla otra vez.
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from pathlib import Path

from app.application.ports import Animator, BackgroundStore, CredentialStore, EventLog
from app.domain.animation import (
    GEMINI_OMNI,
    VideoProvider,
    animation_name,
    animation_prompt,
    new_animation_key,
    validate_seconds,
)
from app.domain.background import is_image
from app.domain.errors import AnimatorError, DomainError, NotFoundError, ValidationError
from app.domain.events import ANIMATION_COMPLETED, ANIMATION_FAILED, ANIMATION_REQUESTED, ANIMATION_TERMINAL, Event
from app.domain.illustration import GeneratedImage, validate_description, validate_guide

CONSUMER_GROUP = "animator"


class AnimationUseCases:
    def __init__(
        self,
        events: EventLog,
        credentials: CredentialStore,
        animator: Animator,
        store: BackgroundStore,
        provider: VideoProvider = GEMINI_OMNI,
    ) -> None:
        self._events = events
        self._credentials = credentials
        self._animator = animator
        self._store = store
        self._provider = provider

    def model(self) -> str:
        return (self._credentials.get(self._provider.model_env) or "").strip() or self._provider.model

    def settings(self) -> dict:
        """Con qué se anima, cuánto cuesta más o menos y si está lista la clave."""
        provider = self._provider
        return {
            "provider": provider.id,
            "name": provider.name,
            "model": self.model(),
            "resolution": provider.resolution,
            "usd_per_second": provider.usd_per_second,
            "ready": bool(self._credentials.get(provider.key_env)),
            "key": provider.key_env,
        }

    # Desde la API ------------------------------------------------------------ #

    def request(
        self,
        topic: str,
        source: str,
        seconds: object,
        description: str = "",
        look: str = "",
        characters: list[Mapping] | None = None,
        seed: int | None = None,
    ) -> Event:
        """
        Encola la animación de una imagen de la galería y devuelve el evento
        con la clave del trabajo. La descripción y la guía del video (estilo y
        reparto) ayudan al modelo a saber qué debe moverse y cómo.
        """
        source = self._animatable(source)
        seconds = validate_seconds(seconds)
        description = validate_description(description, required=False)
        guide = validate_guide(look, characters, seed)
        if not self._credentials.get(self._provider.key_env):
            raise ValidationError(
                f"Para animar escenas hace falta la clave de Google ({self._provider.key_env}) "
                "con la facturación activada: Gemini Omni no tiene nivel gratuito. "
                "Ponla en «Generador de imágenes» → Google."
            )
        return self._events.publish(
            ANIMATION_REQUESTED,
            new_animation_key(),
            {
                "topic": topic.strip(),
                "source": source,
                "seconds": seconds,
                "description": description,
                **guide.as_dict(),
                "provider": self._provider.id,
                "model": self.model(),
            },
        )

    # Desde el consumidor ------------------------------------------------------ #

    def animate(self, key: str, payload: Mapping) -> str:
        """Anima la imagen ahora, bloqueando, y deja el clip en la galería. Devuelve su nombre."""
        source = payload.get("source") or ""
        data = self._store.read(source)
        if not data:
            # Borrada de la galería entre el encargo y el turno del animador.
            raise AnimatorError(f"«{source}» ya no está en la galería: no hay nada que animar.")
        guide = validate_guide(payload.get("look"), payload.get("characters"), payload.get("seed"))
        clip = self._animator.animate(
            self._provider,
            payload.get("model") or self.model(),
            {self._provider.key_env: self._credentials.get(self._provider.key_env)},
            GeneratedImage(data, Path(source).suffix.lower()),
            animation_prompt(payload.get("description") or "", guide),
            int(payload.get("seconds") or 0),
        )
        return self._store.save(animation_name(source, key), io.BytesIO(clip.data))

    def handle_request(self, event: Event) -> None:
        """Atiende un `animation.requested` y publica su desenlace."""
        # Entrega al menos una vez y consumidores que compiten, como las imágenes.
        if event.key is None or self._events.settled(event.key, ANIMATION_TERMINAL):
            return
        if not self._events.claim(event.key):
            return

        try:
            name = self.animate(event.key, event.payload)
        except DomainError as exc:
            self._events.publish(ANIMATION_FAILED, event.key, {"detail": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 - el consumidor no debe morir nunca
            self._events.publish(ANIMATION_FAILED, event.key, {"detail": f"{type(exc).__name__}: {exc}"})
            return

        self._events.publish(
            ANIMATION_COMPLETED,
            event.key,
            {
                "name": name,
                "source": event.payload.get("source"),
                "seconds": event.payload.get("seconds"),
                "model": event.payload.get("model"),
            },
        )

    # ------------------------------------------------------------------------ #

    def _animatable(self, name: str) -> str:
        """La imagen de la galería que se quiere animar, comprobada antes de encolar."""
        name = (name or "").strip()
        if not name:
            raise ValidationError("Elige la imagen que quieres animar.")
        if not is_image(name):
            raise ValidationError("Solo se animan imágenes: un clip de video ya se mueve.")
        if not self._store.has(name):
            raise NotFoundError(f"«{name}» ya no está en la galería.")
        return name
