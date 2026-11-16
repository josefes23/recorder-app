"""Anthropic va por su SDK, no por la capa compatible con OpenAI."""

from __future__ import annotations

from app.domain.errors import WriterError
from app.domain.illustration import GeneratedImage
from app.infrastructure.llm.vision import as_base64


def compose(
    api_key: str | None, model: str, system: str, prompt: str, image: GeneratedImage | None = None
) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": user_content(prompt, image)}]

    def create(**extra):
        return client.messages.create(model=model, max_tokens=4096, system=system, messages=messages, **extra)

    try:
        try:
            # Esfuerzo medio: cien palabras —o un veredicto sobre una imagen—
            # no necesitan que el modelo se lo piense mucho, y así contesta
            # antes y más barato.
            response = create(output_config={"effort": "medium"})
        except anthropic.BadRequestError as exc:
            # La generación 4.5 (Haiku 4.5, Sonnet 4.5) rechaza `effort` con un
            # 400. Se repite sin él antes que mantener una lista de modelos.
            if "effort" not in str(exc):
                raise
            response = create()
    except anthropic.AuthenticationError:
        raise WriterError("La API key de Anthropic no es válida.") from None
    except anthropic.NotFoundError:
        raise WriterError(
            f"Anthropic no conoce el modelo «{model}». Elige otro en «Modelo del guion»."
        ) from None
    except anthropic.BadRequestError as exc:
        raise WriterError(f"Anthropic rechazó la petición: {exc.message}") from None
    except anthropic.RateLimitError:
        raise WriterError("Límite de peticiones alcanzado. Prueba en un momento.") from None
    except anthropic.APIConnectionError:
        raise WriterError("Sin conexión con la API de Anthropic.") from None

    # En Opus 5 los clasificadores pueden declinar: llega HTTP 200 con
    # stop_reason "refusal" y content vacío, así que hay que mirarlo antes.
    if response.stop_reason == "refusal":
        raise WriterError(
            "Claude declinó escribir sobre este tema. Reformúlalo o escribe el guion a mano."
        )

    return "".join(block.text for block in response.content if block.type == "text")


def user_content(prompt: str, image: GeneratedImage | None = None) -> str | list[dict]:
    """El turno del usuario: el encargo, con la imagen delante si la hay."""
    if image is None:
        return prompt
    data, media_type = as_base64(image)
    return [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
        {"type": "text", "text": prompt},
    ]


def catalog(api_key: str | None) -> list[dict] | None:
    """Catálogo vivo. Necesita clave; sin ella (o si falla) devuelve None."""
    if not api_key:
        return None
    try:
        import anthropic

        return [
            {"id": m.id, "label": m.display_name, "group": "Modelos"}
            for m in anthropic.Anthropic(api_key=api_key).models.list()
        ]
    except Exception:  # noqa: BLE001 - sin catálogo vivo se sigue con el de respaldo
        return None
