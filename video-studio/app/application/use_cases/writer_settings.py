"""Qué proveedor redacta, con qué modelo y con qué clave."""

from __future__ import annotations

from app.application.ports import CredentialStore, ScriptComposer
from app.domain.errors import ValidationError
from app.domain.writer import (
    PROVIDER_SETTING,
    PROVIDERS,
    Provider,
    mask_key,
    provider_by_id,
    short_label,
)


class WriterSettings:
    def __init__(self, credentials: CredentialStore, composer: ScriptComposer) -> None:
        self._credentials = credentials
        self._composer = composer

    def chosen(self) -> Provider | None:
        """El que marcó el usuario, tenga clave o no."""
        return provider_by_id(self._credentials.get(PROVIDER_SETTING))

    def active(self) -> Provider | None:
        """El proveedor que va a redactar, o None si no hay ninguna clave.

        El elegido solo manda si tiene clave; si no, se cae al primero que la
        tenga, antes que dejar el botón «Escribir» activo para que falle al
        pulsarlo.
        """
        chosen = self.chosen()
        if chosen and self.api_key(chosen):
            return chosen
        for provider in PROVIDERS:
            if self.api_key(provider):
                return provider
        return None

    def available(self) -> bool:
        return self.active() is not None

    def api_key(self, provider: Provider) -> str | None:
        return self._credentials.get(provider.key_env)

    def model_for(self, provider: Provider) -> str:
        return self._credentials.get(provider.model_env) or provider.default_model

    def label(self) -> str | None:
        provider = self.active()
        return short_label(provider, self.model_for(provider)) if provider else None

    def settings(self) -> dict:
        """Todo lo que la interfaz necesita para pintar el panel de ajustes."""
        # El formulario muestra el proveedor elegido aunque le falte la clave: es
        # justo el caso en el que el usuario abre el panel para ponérsela.
        shown = self.chosen() or self.active() or PROVIDERS[0]
        return {
            "provider": shown.id,
            "label": self.label(),
            "providers": [
                {
                    "id": provider.id,
                    "name": provider.name,
                    "note": provider.note,
                    "key_env": provider.key_env,
                    "key_hint": mask_key(self.api_key(provider)),
                    "model": self.model_for(provider),
                    "models": self._composer.catalog(provider, self.api_key(provider)),
                }
                for provider in PROVIDERS
            ],
        }

    def save(self, provider_id: str, api_key: str = "", model: str = "") -> dict:
        """Guarda proveedor, clave y modelo. Una clave vacía deja la que hubiera."""
        provider = provider_by_id(provider_id)
        if provider is None:
            raise ValidationError(f"Proveedor desconocido: {provider_id}")

        values: dict[str, str | None] = {PROVIDER_SETTING: provider.id}
        if api_key.strip():
            values[provider.key_env] = api_key.strip()
        if model.strip():
            values[provider.model_env] = model.strip()

        self._credentials.save(values)
        return self.settings()
