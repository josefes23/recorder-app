"""
Biblioteca de elementos que se repiten entre videos (`domain.saved_characters`).

Guardar uno lo deja en la biblioteca al momento y encarga su imagen de
referencia, que tarda como cualquier otra imagen, así que llega por el flujo de
eventos como las escenas. Volver a guardar el mismo nombre actualiza sus
rasgos; si cambiaron, se repinta la referencia.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from app.application.ports import CharacterRepository, EventLog, ReferenceStore
from app.application.use_cases.illustrations import ImageSettings, ReviewedPainter, parse_time
from app.domain.errors import DomainError, IllustratorError, NotFoundError, ValidationError
from app.domain.events import (
    REFERENCE_COMPLETED,
    REFERENCE_FAILED,
    REFERENCE_REQUESTED,
    REFERENCE_TERMINAL,
    Event,
    new_job_key,
)
from app.domain.illustration import image_provider_by_id, validate_character
from app.domain.saved_characters import (
    SavedCharacter,
    reference_description,
    reference_name,
    reference_prompt,
)

CONSUMER_GROUP = "referencer"


class CharacterUseCases:
    def __init__(
        self,
        events: EventLog,
        repository: CharacterRepository,
        references: ReferenceStore,
        settings: ImageSettings,
        painter: ReviewedPainter,
    ) -> None:
        self._events = events
        self._repository = repository
        self._references = references
        self._settings = settings
        self._painter = painter

    # Desde la API ------------------------------------------------------------ #

    def list(self) -> list[dict]:
        return [c.as_dict() for c in self._repository.list()]

    def save(
        self,
        name: str,
        traits: str,
        kind: str = "",
        look: str = "",
        provider_id: str = "",
        model: str = "",
    ) -> tuple[SavedCharacter, Event | None]:
        """
        Lo guarda (o lo actualiza, si ya hay uno con ese nombre) y encarga su
        imagen de referencia si no la tiene o si cambiaron sus rasgos. Devuelve
        el elemento y el encargo, o None si la referencia que tiene sigue valiendo.
        """
        character = validate_character({"name": name, "traits": traits, "kind": kind})
        if character is None:
            raise ValidationError("Cada personaje o elemento necesita un nombre y sus rasgos.")
        # Antes de tocar la biblioteca: sin generador no se guarda a medias.
        provider = self._provider(provider_id, model)
        before = self._repository.find(character.name)
        saved = self._repository.upsert(character)
        unchanged = before and before.reference and (before.traits, before.kind) == (saved.traits, saved.kind)
        if unchanged:
            return saved, None
        return saved, self._request(saved, look, *provider)

    def repaint(self, character_id: int, look: str = "", provider_id: str = "", model: str = "") -> Event:
        """Pide otra imagen de referencia para uno ya guardado."""
        saved = self._get(character_id)
        return self._request(saved, look, *self._provider(provider_id, model))

    def remove(self, character_id: int) -> None:
        saved = self._get(character_id)
        self._repository.remove(character_id)
        if saved.reference:
            self._references.remove(saved.reference)

    def reference_file(self, name: str) -> Path:
        path = self._references.path(name)
        if path is None:
            raise NotFoundError(f"No existe la imagen de referencia {name}.")
        return path

    # Desde el consumidor ------------------------------------------------------ #

    def handle_request(self, event: Event) -> None:
        """Atiende un `reference.requested` y publica su desenlace."""
        if event.key is None or self._events.settled(event.key, REFERENCE_TERMINAL):
            return
        if not self._events.claim(event.key):
            return
        try:
            payload = self._paint(event.payload, parse_time(event.created_at))
        except DomainError as exc:
            self._events.publish(REFERENCE_FAILED, event.key, {"detail": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 - el consumidor no debe morir nunca
            self._events.publish(REFERENCE_FAILED, event.key, {"detail": f"{type(exc).__name__}: {exc}"})
            return
        self._events.publish(REFERENCE_COMPLETED, event.key, payload)

    # ------------------------------------------------------------------------ #

    def _paint(self, payload: Mapping, requested_at) -> dict:
        provider = image_provider_by_id(payload.get("provider"))
        if provider is None:
            raise IllustratorError(f"Generador desconocido: {payload.get('provider')}")
        saved = self._repository.get(int(payload.get("id") or 0))
        if saved is None:
            raise NotFoundError("Ese elemento ya no está en la biblioteca.")

        character = saved.as_character()
        image, report = self._painter.paint(
            provider,
            payload.get("model") or "",
            reference_prompt(character, payload.get("look") or ""),
            reference_description(character),
            None,
            payload.get("review"),
            requested_at,
        )
        name = reference_name(saved.id, image.extension)
        self._references.save(name, image.data)
        # Si la anterior era de otro formato (.png → .jpg), no se queda huérfana.
        if saved.reference and saved.reference != name:
            self._references.remove(saved.reference)
        self._repository.set_reference(saved.id, name)
        return {"id": saved.id, "reference": name, "review": report.as_dict() if report else None}

    def _request(self, saved: SavedCharacter, look: str, provider_id: str, model: str) -> Event:
        return self._events.publish(
            REFERENCE_REQUESTED,
            new_job_key("rf"),
            {
                "id": saved.id,
                "look": " ".join((look or "").split()),
                "provider": provider_id,
                "model": model,
                "review": self._painter.choose_reviewer(),
            },
        )

    def _provider(self, provider_id: str, model: str) -> tuple[str, str]:
        provider = self._settings.resolve(provider_id)
        model = model.strip() or self._settings.model_for(provider)
        if not provider.has_model(model):
            raise ValidationError(f"{provider.name} no ofrece el modelo «{model}».")
        return provider.id, model

    def _get(self, character_id: int) -> SavedCharacter:
        saved = self._repository.get(character_id)
        if saved is None:
            raise NotFoundError("Ese elemento ya no está en la biblioteca.")
        return saved
