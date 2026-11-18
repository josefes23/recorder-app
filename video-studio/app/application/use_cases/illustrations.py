"""
Escenas ilustradas: qué generador pinta, con qué datos, y los encargos de
imagen.

Como el guion, una imagen tarda —de dos segundos a medio minuto según el
generador— y un guion entero pide varias, así que la petición HTTP solo
publica el encargo y la imagen llega por el flujo de eventos. Al terminar se
guarda en la galería como un fondo más: el render no distingue una imagen
generada de un clip de Pexels.

Antes de guardarla, el modelo del guion la revisa si ve imágenes
(`domain.review`): con un fallo a la vista se repinta con otra semilla. A la
galería solo llega la que se queda.

Corregir una imagen es el mismo encargo con dos datos más: cuál y qué está
mal. El generador recibe la imagen como primera referencia y la edita, y el
revisor comprueba además que el fallo ya no está.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path

from app.application.ports import (
    BackgroundStore,
    CharacterRepository,
    CredentialStore,
    EventLog,
    Illustrator,
    ReferenceStore,
    ScriptComposer,
)
from app.application.use_cases.writer_settings import WriterSettings
from app.application.use_cases.prompts import PromptBook
from app.domain import review as quality
from app.domain.background import is_image
from app.domain.errors import DomainError, IllustratorError, NotFoundError, ValidationError
from app.domain.events import (
    ILLUSTRATION_COMPLETED,
    ILLUSTRATION_FAILED,
    ILLUSTRATION_REQUESTED,
    ILLUSTRATION_TERMINAL,
    Event,
)
from app.domain.illustration import (
    DEFAULT_STYLE,
    IMAGE_PROVIDERS,
    MAX_REFERENCES,
    PROVIDER_SETTING,
    Character,
    GeneratedImage,
    ImageProvider,
    cast_in,
    correction_prompt,
    illustration_name,
    image_prompt,
    image_provider_by_id,
    new_illustration_key,
    validate_correction,
    validate_description,
    validate_guide,
)
from app.domain.production import format_by_id
from app.domain.review import ReviewReport
from app.domain.writer import mask_key, provider_by_id, short_label

CONSUMER_GROUP = "illustrator"


class ImageSettings:
    """Qué generador de imágenes se usa, con qué modelo y con qué datos."""

    def __init__(self, credentials: CredentialStore) -> None:
        self._credentials = credentials

    def chosen(self) -> ImageProvider | None:
        return image_provider_by_id(self._credentials.get(PROVIDER_SETTING))

    def ready(self, provider: ImageProvider) -> bool:
        return all(self._credentials.get(f.env) for f in provider.fields)

    def active(self) -> ImageProvider | None:
        """El elegido si tiene todos sus datos; si no, el primero que los tenga."""
        chosen = self.chosen()
        if chosen and self.ready(chosen):
            return chosen
        return next((p for p in IMAGE_PROVIDERS if self.ready(p)), None)

    def credentials_for(self, provider: ImageProvider) -> dict[str, str | None]:
        return {f.env: self._credentials.get(f.env) for f in provider.fields}

    def model_for(self, provider: ImageProvider) -> str:
        saved = self._credentials.get(provider.model_env)
        # Un modelo guardado que ya no está en la lista no se arrastra.
        return saved if saved and provider.has_model(saved) else provider.default_model

    def label(self) -> str | None:
        provider = self.active()
        if provider is None:
            return None
        model = self.model_for(provider)
        name = next(m.label for m in provider.models if m.id == model)
        return f"{provider.name.split()[0]} · {name}"

    def settings(self) -> dict:
        shown = self.chosen() or self.active() or IMAGE_PROVIDERS[0]
        return {
            "provider": shown.id,
            "label": self.label(),
            "style": DEFAULT_STYLE,
            "providers": [
                {
                    "id": provider.id,
                    "name": provider.name,
                    "note": provider.note,
                    "ready": self.ready(provider),
                    "fields": [
                        {
                            "env": f.env,
                            "label": f.label,
                            "secret": f.secret,
                            "hint": self._hint(f.env, f.secret),
                        }
                        for f in provider.fields
                    ],
                    "model": self.model_for(provider),
                    "models": [{"id": m.id, "label": m.label, "note": m.note} for m in provider.models],
                }
                for provider in IMAGE_PROVIDERS
            ],
        }

    def save(self, provider_id: str, model: str = "", values: Mapping[str, str] | None = None) -> dict:
        """Guarda generador, modelo y datos. Un dato vacío deja el que hubiera."""
        provider = image_provider_by_id(provider_id)
        if provider is None:
            raise ValidationError(f"Generador desconocido: {provider_id}")
        if model.strip() and not provider.has_model(model.strip()):
            raise ValidationError(f"{provider.name} no ofrece el modelo «{model.strip()}».")

        allowed = {f.env for f in provider.fields}
        updates: dict[str, str | None] = {PROVIDER_SETTING: provider.id}
        for env, value in (values or {}).items():
            if env not in allowed:
                raise ValidationError(f"{provider.name} no usa {env}.")
            if value.strip():
                updates[env] = value.strip()
        if model.strip():
            updates[provider.model_env] = model.strip()

        self._credentials.save(updates)
        return self.settings()

    def resolve(self, provider_id: str = "") -> ImageProvider:
        """El generador pedido, o el activo si no se pide ninguno. Sin datos, un error que dice cuáles faltan."""
        if not provider_id.strip():
            provider = self.active()
            if provider is None:
                raise ValidationError(
                    "No hay ningún generador de imágenes configurado. Añade sus datos en "
                    "«Generador de imágenes»."
                )
            return provider

        provider = image_provider_by_id(provider_id)
        if provider is None:
            raise ValidationError(f"Generador desconocido: {provider_id}")
        if not self.ready(provider):
            missing = [f.label.lower() for f in provider.fields if not self.credentials_for(provider)[f.env]]
            raise ValidationError(
                f"A {provider.name} le falta {' y '.join(missing)}. Añádelo en «Generador de imágenes»."
            )
        return provider

    def _hint(self, env: str, secret: bool) -> str | None:
        value = self._credentials.get(env)
        if not value:
            return None
        # Un ID de cuenta no es secreto y se reconoce mejor entero.
        return mask_key(value) if secret else value


class ReviewedPainter:
    """
    Pinta una imagen y, si el modelo del guion ve imágenes, la revisa y la
    repinta con otra semilla mientras vea fallos (`domain.review`).

    Lo usan las escenas y las imágenes de referencia de la biblioteca: una
    referencia con una mano de más estropearía todas las escenas donde sale.
    """

    def __init__(
        self,
        settings: ImageSettings,
        illustrator: Illustrator,
        writer: WriterSettings,
        reviewer: ScriptComposer,
        clock: Callable[[], datetime] = datetime.now,
        prompts: PromptBook | None = None,
    ) -> None:
        self._prompts = prompts or PromptBook()
        self._settings = settings
        self._illustrator = illustrator
        self._writer = writer
        self._reviewer = reviewer
        # Hora local, como `created_at` en el log de eventos.
        self._clock = clock

    def now(self) -> datetime:
        return self._clock()

    def choose_reviewer(self) -> dict | None:
        """Quién revisaría una imagen pedida ahora: el modelo del guion, si ve imágenes."""
        provider = self._writer.active()
        if provider is None or not provider.sees_images:
            return None
        return {"provider": provider.id, "model": self._writer.model_for(provider)}

    def paint(
        self,
        provider: ImageProvider,
        model: str,
        prompt: str,
        description: str,
        seed: int | None,
        review: object,
        started: datetime | None = None,
        references: Sequence[GeneratedImage] = (),
        correction: str = "",
        aspect: str = "9:16",
    ) -> tuple[GeneratedImage, ReviewReport | None]:
        """
        Con revisor (`review`, lo que eligió `choose_reviewer` al encargarla),
        repinta mientras vea fallos, hasta `review.MAX_ATTEMPTS` imágenes o
        hasta que el encargo lleve demasiado esperando. Devuelve la imagen que
        se queda y lo que dijo el revisor.

        Con `correction`, el revisor comprueba además que se arregló.
        """
        reviewer = self._reviewer_for(review)
        started = started or self._clock()

        shots: list[tuple[GeneratedImage, quality.Review]] = []
        while True:
            attempt_seed = quality.retry_seed(seed, len(shots))
            try:
                image = self._paint_once(provider, model, prompt, attempt_seed, references, aspect)
            except DomainError:
                if not shots:
                    raise
                break  # el generador falló al repintar: vale la mejor que ya había

            if reviewer is None:
                return image, None
            label, check = reviewer
            try:
                verdict = check(image, description, correction)
            except Exception as exc:  # noqa: BLE001 - una revisión fallida nunca tumba la imagen
                detail = str(exc) if isinstance(exc, DomainError) else f"{type(exc).__name__}: {exc}"
                return image, quality.unchecked(label, len(shots) + 1, detail)

            shots.append((image, verdict))
            if verdict.ok or not quality.may_retry(len(shots), started, self._clock()):
                break

        reviews = [verdict for _, verdict in shots]
        kept, _ = shots[quality.pick(reviews)]
        return kept, quality.report(reviewer[0], reviews)

    def _paint_once(
        self,
        provider: ImageProvider,
        model: str,
        prompt: str,
        seed: int | None,
        references: Sequence[GeneratedImage],
        aspect: str = "9:16",
    ) -> GeneratedImage:
        image = self._illustrator.illustrate(
            provider,
            model or self._settings.model_for(provider),
            self._settings.credentials_for(provider),
            prompt,
            seed,
            references,
            aspect,
        )
        if not image.data:
            raise IllustratorError(f"{provider.name} devolvió una imagen vacía. Vuelve a intentarlo.")
        return image

    def _reviewer_for(self, chosen: object):
        """(etiqueta, función que revisa) para el revisor del encargo, o None."""
        if not isinstance(chosen, Mapping):
            return None
        provider = provider_by_id(chosen.get("provider"))
        model = str(chosen.get("model") or "")
        if provider is None or not provider.sees_images or not model:
            return None

        def check(image: GeneratedImage, description: str, correction: str) -> quality.Review:
            raw = self._reviewer.compose(
                provider,
                model,
                self._writer.api_key(provider),
                self._prompts.template("review") or quality.SYSTEM_PROMPT,
                quality.review_prompt(description, correction),
                image,
            )
            return quality.parse_review(raw)

        return short_label(provider, model), check


class IllustrationUseCases:
    def __init__(
        self,
        events: EventLog,
        settings: ImageSettings,
        painter: ReviewedPainter,
        store: BackgroundStore,
        characters: CharacterRepository,
        references: ReferenceStore,
        prompts: PromptBook | None = None,
    ) -> None:
        self._prompts = prompts or PromptBook()
        self._events = events
        self._settings = settings
        self._painter = painter
        self._store = store
        self._characters = characters
        self._references = references

    # Desde la API ------------------------------------------------------------ #

    def request(
        self,
        topic: str,
        description: str,
        look: str = "",
        characters: list[Mapping] | None = None,
        seed: int | None = None,
        provider_id: str = "",
        model: str = "",
        review: bool = True,
        source: str = "",
        correction: str = "",
        format: str = "9:16",
    ) -> Event:
        """
        Encola una imagen y devuelve el evento con la clave del trabajo.

        El estilo, el reparto y la semilla son la guía visual del video: viajan
        con cada encargo para que la escena case con las demás. Quién revisa se
        decide aquí, como quién pinta: el modelo del guion si ve imágenes.

        Con `source` (una imagen de la galería) y `correction` (qué está mal),
        no se pinta otra: se corrige esa. La original se queda en la galería y
        la corregida llega con nombre propio, así que se puede volver atrás.
        """
        fixing = bool(source.strip() or correction.strip())
        if fixing:
            correction = validate_correction(correction)
            source = self._correctable(source)
        description = validate_description(description, required=not fixing)
        guide = validate_guide(look, characters, seed)
        fmt = format_by_id(format)
        provider = self._settings.resolve(provider_id)
        model = model.strip() or self._settings.model_for(provider)
        if not provider.has_model(model):
            raise ValidationError(f"{provider.name} no ofrece el modelo «{model}».")
        return self._events.publish(
            ILLUSTRATION_REQUESTED,
            new_illustration_key(),
            {
                "topic": topic.strip(),
                "description": description,
                **guide.as_dict(),
                "provider": provider.id,
                "model": model,
                "review": self._painter.choose_reviewer() if review else None,
                "format": fmt.id,
                **({"source": source, "correction": correction} if fixing else {}),
            },
        )

    # Desde el consumidor ------------------------------------------------------ #

    def illustrate(
        self, key: str, payload: Mapping, requested_at: datetime | None = None
    ) -> tuple[str, ReviewReport | None]:
        """
        Pinta la imagen ahora, bloqueando, y la deja en la galería. Los
        elementos de la biblioteca que salen en la escena llevan su imagen de
        referencia. Devuelve el nombre en la galería y lo que dijo el revisor.

        Si el encargo es una corrección, la imagen a corregir va delante de
        esas referencias y el encargo pide editarla, no pintar otra.
        """
        provider = image_provider_by_id(payload.get("provider"))
        if provider is None:
            raise IllustratorError(f"Generador desconocido: {payload.get('provider')}")
        description = payload.get("description", "")
        correction = payload.get("correction") or ""
        guide = validate_guide(payload.get("look"), payload.get("characters"), payload.get("seed"))
        fmt = format_by_id(payload.get("format"))

        if correction:
            original = self._original(payload.get("source") or "")
            referenced, references = self._references_for(
                cast_in(f"{description} {correction}", guide.characters), MAX_REFERENCES - 1
            )
            prompt = correction_prompt(
                correction, description, guide, referenced, self._prompts.template("correction")
            )
            references = [original, *references]
        else:
            referenced, references = self._references_for(cast_in(description, guide.characters))
            prompt = image_prompt(description, guide, referenced, fmt.framing, self._prompts.template("image"))

        image, report = self._painter.paint(
            provider,
            payload.get("model") or "",
            prompt,
            description,
            guide.seed,
            payload.get("review"),
            requested_at,
            references,
            correction=correction,
            aspect=fmt.id,
        )
        name = illustration_name(payload.get("topic", ""), key, image.extension)
        return self._store.save(name, io.BytesIO(image.data)), report

    def handle_request(self, event: Event) -> None:
        """Atiende un `illustration.requested` y publica su desenlace."""
        # Mismas garantías que el guion: con entrega al menos una vez el encargo
        # puede llegar dos veces, y varios consumidores compiten por él.
        if event.key is None or self._events.settled(event.key, ILLUSTRATION_TERMINAL):
            return
        if not self._events.claim(event.key):
            return

        try:
            name, report = self.illustrate(event.key, event.payload, parse_time(event.created_at))
        except DomainError as exc:
            self._events.publish(ILLUSTRATION_FAILED, event.key, {"detail": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 - el consumidor no debe morir nunca
            self._events.publish(ILLUSTRATION_FAILED, event.key, {"detail": f"{type(exc).__name__}: {exc}"})
            return

        self._events.publish(
            ILLUSTRATION_COMPLETED,
            event.key,
            {
                "name": name,
                "provider": event.payload.get("provider"),
                "model": event.payload.get("model"),
                "review": report.as_dict() if report else None,
            },
        )

    # ------------------------------------------------------------------------ #

    def _correctable(self, name: str) -> str:
        """La imagen de la galería que se quiere corregir, comprobada antes de encolar."""
        name = name.strip()
        if not name:
            raise ValidationError("Elige la imagen que quieres corregir.")
        if not is_image(name):
            raise ValidationError("Solo se pueden corregir imágenes: un clip de video no se repinta.")
        if not self._store.has(name):
            raise NotFoundError(f"«{name}» ya no está en la galería.")
        return name

    def _original(self, name: str) -> GeneratedImage:
        data = self._store.read(name)
        if not data:
            # Borrada de la galería entre el encargo y el turno del ilustrador.
            raise IllustratorError(f"«{name}» ya no está en la galería: no hay nada que corregir.")
        return GeneratedImage(data, Path(name).suffix.lower())

    def _references_for(
        self, cast: Sequence[Character], limit: int = MAX_REFERENCES
    ) -> tuple[list[Character], list[GeneratedImage]]:
        """
        Los elementos de la escena que vienen de la biblioteca y tienen imagen
        de referencia, con esas imágenes en el mismo orden. Uno borrado de la
        biblioteca después de pedir la escena simplemente va sin referencia.
        """
        referenced: list[Character] = []
        images: list[GeneratedImage] = []
        for character in cast:
            if len(images) == limit:
                break
            saved = self._characters.get(character.saved) if character.saved else None
            data = self._references.read(saved.reference) if saved and saved.reference else None
            if data:
                referenced.append(character)
                images.append(GeneratedImage(data, Path(saved.reference).suffix))
        return referenced, images


def parse_time(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None
