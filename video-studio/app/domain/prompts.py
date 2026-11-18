"""
Los prompts que el estudio manda por debajo, para verlos y editarlos.

Cada uno es una plantilla con variables (`domain.template`): el texto fijo se
edita; las variables las rellena el programa con los datos del video. Aquí
vive el catálogo —qué prompts hay, para qué sirve cada uno, qué variables
admite— y el ejemplo que se enseña mientras se edita.

Lo que se edita es siempre la parte de instrucciones. Lo que viaja como datos
(el tema, las frases del guion numeradas) lo monta el programa y se enseña en
el ejemplo como «mensaje del usuario», sin poder tocarlo.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.domain.animation import ANIMATION_TEMPLATE, animation_prompt
from app.domain.cover import TITLES_SYSTEM_PROMPT, build_titles_prompt
from app.domain.description import DESCRIPTION_SYSTEM_PROMPT, build_description_prompt
from app.domain.errors import ValidationError
from app.domain.illustration import (
    CORRECTION_TEMPLATE,
    IMAGE_TEMPLATE,
    Character,
    VisualGuide,
    correction_prompt,
    image_prompt,
)
from app.domain.production import REEL, VERTICAL
from app.domain.review import SYSTEM_PROMPT as REVIEW_PROMPT
from app.domain.review import review_prompt
from app.domain.saved_characters import REFERENCE_TEMPLATE, reference_prompt
from app.domain.storyboard import STORYBOARD_TEMPLATE
from app.domain.storyboard import build_prompt as storyboard_user
from app.domain.storyboard import system_prompt as storyboard_system
from app.domain.template import variables_in
from app.domain.writer import (
    DIALOGUE_RULE,
    SCRIPT_TEMPLATE,
    system_prompt as script_system,
)
from app.domain.writer import build_prompt as script_user

#: Un prompt de más de esto es un error de pegado, no un prompt.
PROMPT_LIMIT = 20_000


@dataclass(frozen=True)
class Variable:
    name: str
    help: str


@dataclass(frozen=True)
class Example:
    """Un prompt ya montado con datos de ejemplo."""

    label: str
    text: str


@dataclass(frozen=True)
class PromptSpec:
    id: str
    name: str
    #: A qué modelo va: «texto», «imagen» o «video».
    group: str
    #: Cuándo se manda, en una frase.
    when: str
    default: str
    variables: tuple[Variable, ...] = ()
    #: Sin estas el prompt pierde su sentido: se avisa, no se impide.
    required: tuple[str, ...] = ()
    #: Qué datos van además, aparte, como mensaje del usuario. Solo informa.
    user_part: str = ""
    #: Monta el ejemplo con una plantilla dada: `(plantilla) -> ejemplos`.
    example: Callable[[str], tuple[Example, ...]] = lambda template: ()


_TOPIC = "Los tres hábitos que arruinan tu sueño"
_SENTENCES = (
    "Dormir mal no es mala suerte.",
    "Es cuestión de tres hábitos que repites cada noche.",
    "El primero es mirar el móvil en la cama.",
)
_GUIDE = VisualGuide(
    look="Fotografía cálida de interior, luz de lámpara y tonos ocres.",
    characters=(Character("Ana", "mujer de 30 años, pelo negro corto, jersey verde"),),
)
_SCENE = "Ana mira el móvil en la cama, a oscuras, con la cara iluminada por la pantalla."


def _script(template: str) -> tuple[Example, ...]:
    return (
        Example("Mensaje del sistema", script_system(REEL, False, template=template)),
        Example("Mensaje del usuario", script_user(_TOPIC, "Tono cercano, sin tecnicismos.")),
    )


def _dialogue(template: str) -> tuple[Example, ...]:
    return (Example("Mensaje del sistema (con diálogos)", script_system(REEL, True, dialogue_rule=template)),)


def _storyboard(template: str) -> tuple[Example, ...]:
    return (
        Example("Mensaje del sistema", storyboard_system(VERTICAL, REEL, template)),
        Example("Mensaje del usuario", storyboard_user(_TOPIC, "acuarela suave", _SENTENCES)),
    )


def _image(template: str) -> tuple[Example, ...]:
    return (Example("Prompt de la imagen", image_prompt(_SCENE, _GUIDE, framing=VERTICAL.framing, template=template)),)


def _correction(template: str) -> tuple[Example, ...]:
    text = correction_prompt("la mujer tiene seis dedos", _SCENE, _GUIDE, template=template)
    return (Example("Prompt de la corrección", text),)


def _animation(template: str) -> tuple[Example, ...]:
    text = animation_prompt(_SCENE, _GUIDE, "Ana desliza el dedo por la pantalla; la cámara se acerca", template)
    return (Example("Prompt del clip", text),)


def _reference(template: str) -> tuple[Example, ...]:
    return (Example("Prompt de la referencia", reference_prompt(_GUIDE.characters[0], _GUIDE.look, template)),)


def _titles(template: str) -> tuple[Example, ...]:
    return (
        Example("Mensaje del sistema", template),
        Example("Mensaje del usuario", build_titles_prompt(_TOPIC, " ".join(_SENTENCES))),
    )


def _description(template: str) -> tuple[Example, ...]:
    return (
        Example("Mensaje del sistema", template),
        Example("Mensaje del usuario", build_description_prompt(_TOPIC, "3 *hábitos* que arruinan tu sueño", " ".join(_SENTENCES))),
    )


def _review(template: str) -> tuple[Example, ...]:
    return (
        Example("Mensaje del sistema", template),
        Example("Mensaje del usuario (con la imagen adjunta)", review_prompt(_SCENE)),
    )


_ELEMENTS = Variable("elements", "Los rasgos de cada personaje u objeto que sale en la escena, uno por línea.")
_REFERENCES = Variable("references", "Qué imagen de referencia es de quién. Vacío si no hay.")
_STYLE = Variable("style", "El estilo común del video.")

PROMPTS: tuple[PromptSpec, ...] = (
    PromptSpec(
        "script", "Guion", "texto", "Al pulsar «Escribir con IA» en el paso 1.",
        SCRIPT_TEMPLATE,
        (
            Variable("kind", "Qué se escribe: «Reels y Shorts» o «cortometrajes»."),
            Variable("words_min", "Mínimo de palabras, según la duración elegida."),
            Variable("words_max", "Máximo de palabras, según la duración elegida."),
            Variable("duration", "La duración que producen: «entre 30 y 45 segundos»."),
            Variable("structure", "La forma del guion (gancho, nudo, cierre…) según la duración."),
            Variable("dialogue_rule", "Las reglas del diálogo. Vacío si el guion no es un diálogo."),
            Variable("closing", "Cómo debe devolver el texto (cambia con el diálogo)."),
        ),
        required=("words_min", "words_max"),
        user_part="El tema y las indicaciones adicionales.",
        example=_script,
    ),
    PromptSpec(
        "script_dialogue", "Guion · reglas del diálogo", "texto",
        "Se añade al prompt del guion cuando activas «Guion con diálogos».",
        DIALOGUE_RULE, example=_dialogue,
    ),
    PromptSpec(
        "storyboard", "Guion visual", "texto", "Al pulsar «Proponer escenas» en el paso de escenas.",
        STORYBOARD_TEMPLATE,
        (
            Variable("kind", "El tipo de video: «videos cortos verticales…» o «cortometrajes…»."),
            Variable("frame_rule", "Dónde van las caras según el formato (vertical u horizontal)."),
        ),
        user_part="El tema, el estilo, los personajes que ya hay y el guion en frases numeradas con su duración.",
        example=_storyboard,
    ),
    PromptSpec(
        "image", "Imagen de cada escena", "imagen", "Al pintar la imagen de una escena.",
        IMAGE_TEMPLATE,
        (
            Variable("description", "La descripción de la escena (la del guion visual, o la que editaste)."),
            _ELEMENTS, _REFERENCES, _STYLE,
            Variable("framing", "Cómo se encuadra: depende del formato vertical u horizontal."),
        ),
        required=("description",),
        example=_image,
    ),
    PromptSpec(
        "correction", "Corregir una imagen", "imagen", "Al pedir una corrección de una imagen ya pintada.",
        CORRECTION_TEMPLATE,
        (
            Variable("correction", "Lo que escribes que está mal en la imagen."),
            Variable("scene", "«La escena muestra: …». Vacío si la escena no tiene descripción."),
            _ELEMENTS, _REFERENCES,
        ),
        required=("correction",),
        example=_correction,
    ),
    PromptSpec(
        "reference", "Imagen de referencia de un personaje", "imagen",
        "Al crear la imagen de referencia de un personaje de la biblioteca.",
        REFERENCE_TEMPLATE,
        (
            Variable("framing", "El plano según el tipo: retrato, animal, objeto o lugar."),
            Variable("name", "El nombre del personaje."),
            Variable("traits", "Sus rasgos fijos."),
            _STYLE,
        ),
        example=_reference,
    ),
    PromptSpec(
        "animation", "Animar una escena", "video", "Al animar una escena con Gemini Omni.",
        ANIMATION_TEMPLATE,
        (
            Variable("scene", "«Qué pasa: …». Vacío si la escena no tiene descripción."),
            _ELEMENTS, _STYLE,
            Variable("movement", "Lo que se mueve en la escena y un solo plano; si no hay, un movimiento suave."),
        ),
        example=_animation,
    ),
    PromptSpec(
        "review", "Revisor de imágenes", "texto", "Después de pintar cada imagen, si el modelo del guion ve imágenes.",
        REVIEW_PROMPT,
        user_part="La descripción de la escena (y la corrección pedida, si la hay), con la imagen adjunta.",
        example=_review,
    ),
    PromptSpec(
        "titles", "Títulos de portada", "texto", "Al proponer títulos en la pestaña Portada.",
        TITLES_SYSTEM_PROMPT, user_part="El tema y el guion.", example=_titles,
    ),
    PromptSpec(
        "description", "Descripción para publicar", "texto", "Al escribir la descripción del video.",
        DESCRIPTION_SYSTEM_PROMPT, user_part="El tema, el título de la portada y el guion.", example=_description,
    ),
)

BY_ID = {spec.id: spec for spec in PROMPTS}


def spec_by_id(prompt_id: str) -> PromptSpec:
    spec = BY_ID.get((prompt_id or "").strip())
    if spec is None:
        raise ValidationError(f"No existe el prompt «{prompt_id}».")
    return spec


def validate_prompt(prompt_id: str, text: str | None) -> str:
    spec_by_id(prompt_id)
    body = (text or "").replace("\r\n", "\n").strip("\n")
    if not body.strip():
        raise ValidationError("El prompt no puede quedar vacío. Para volver al original, usa «Restaurar».")
    if len(body) > PROMPT_LIMIT:
        raise ValidationError(f"El prompt es demasiado largo: déjalo por debajo de {PROMPT_LIMIT} caracteres.")
    return body


def warnings(spec: PromptSpec, template: str) -> list[str]:
    """Lo que probablemente no es lo que se quería, sin impedir guardarlo."""
    known = {v.name for v in spec.variables}
    used = set(variables_in(template))
    notes = [f"Falta {{{name}}}: sin ella el prompt pierde ese dato." for name in spec.required if name not in used]
    notes += [
        f"{{{name}}} no es una variable de este prompt: se enviará tal cual."
        for name in variables_in(template)
        if name not in known
    ]
    return notes


def preview(prompt_id: str, template: str | None = None) -> dict:
    """El prompt montado con datos de ejemplo, para ver el efecto de una edición."""
    spec = spec_by_id(prompt_id)
    text = spec.default if template is None else template
    return {
        "examples": [{"label": e.label, "text": e.text} for e in spec.example(text)],
        "warnings": warnings(spec, text),
    }
