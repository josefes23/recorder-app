"""Ver y editar los prompts que se mandan a los modelos."""

from __future__ import annotations

from app.application.ports import PromptStore
from app.domain.prompts import PROMPTS, preview, spec_by_id, validate_prompt, warnings


class MemoryPromptStore:
    """Sin base de datos —las pruebas, o un caso de uso suelto— no hay ediciones."""

    def __init__(self) -> None:
        self._bodies: dict[str, str] = {}

    def all(self) -> dict[str, str]:
        return dict(self._bodies)

    def set(self, prompt_id: str, body: str) -> None:
        self._bodies[prompt_id] = body

    def remove(self, prompt_id: str) -> None:
        self._bodies.pop(prompt_id, None)


class PromptBook:
    def __init__(self, store: PromptStore | None = None) -> None:
        self._store = store or MemoryPromptStore()

    def template(self, prompt_id: str) -> str | None:
        """La versión editada, o None para que mande el original."""
        return self._store.all().get(prompt_id)

    def catalog(self) -> list[dict]:
        edited = self._store.all()
        return [self._describe(spec, edited.get(spec.id)) for spec in PROMPTS]

    def save(self, prompt_id: str, text: str) -> dict:
        spec = spec_by_id(prompt_id)
        body = validate_prompt(prompt_id, text)
        # Guardar el original tal cual no es editar: así «editado» es de fiar.
        if body == spec.default:
            self._store.remove(prompt_id)
            return self._describe(spec, None)
        self._store.set(prompt_id, body)
        return self._describe(spec, body)

    def reset(self, prompt_id: str) -> dict:
        spec = spec_by_id(prompt_id)
        self._store.remove(prompt_id)
        return self._describe(spec, None)

    def preview(self, prompt_id: str, template: str | None) -> dict:
        spec_by_id(prompt_id)
        return preview(prompt_id, template if template is not None else self.template(prompt_id))

    @staticmethod
    def _describe(spec, edited: str | None) -> dict:
        current = edited if edited is not None else spec.default
        return {
            "id": spec.id,
            "name": spec.name,
            "group": spec.group,
            "when": spec.when,
            "user_part": spec.user_part,
            "variables": [{"name": v.name, "help": v.help} for v in spec.variables],
            "default": spec.default,
            "text": current,
            "edited": edited is not None,
            **preview(spec.id, current),
        }
