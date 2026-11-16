"""
Escenas ilustradas: quién pinta las imágenes, cómo se trocea el guion en
escenas y qué se le pide a cada imagen.

Aquí viven las reglas; cómo se habla con cada API es de
`infrastructure.imaging`. Añadir un generador es añadir una entrada a
IMAGE_PROVIDERS y enseñarle al ilustrador a llamarlo.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import uuid4

from app.domain.errors import ValidationError
from app.domain.script import WORDS_PER_SECOND, clean_script
from app.domain.stock import slugify

# Variable del .env que guarda el generador elegido en la interfaz.
PROVIDER_SETTING = "IMAGE_PROVIDER"

#: Cuánto dura, de media, una escena generada desde el guion. Por debajo de
#: cinco segundos la imagen apenas se ve; por encima de ocho el zoom lento del
#: motor ya no basta para que la pantalla no parezca parada.
SECONDS_PER_SCENE = 6.0

#: Tope de imágenes por guion: cada una cuesta tiempo y, según el generador,
#: dinero o cupo diario.
MAX_SCENES = 8

DEFAULT_STYLE = "fotografía cinematográfica realista, luz natural, colores cálidos"


@dataclass(frozen=True)
class KeyField:
    """Un dato que el generador necesita guardado en el .env."""

    env: str
    label: str
    #: Se enmascara al enseñarlo: es una clave, no un identificador.
    secret: bool = True


@dataclass(frozen=True)
class ImageModel:
    id: str
    label: str
    #: Coste o cupo, para elegir con conocimiento.
    note: str


@dataclass(frozen=True)
class ImageProvider:
    id: str
    name: str
    note: str
    fields: tuple[KeyField, ...]
    #: Variable del .env donde se guarda el modelo elegido.
    model_env: str
    models: tuple[ImageModel, ...]

    @property
    def default_model(self) -> str:
        return self.models[0].id

    def has_model(self, model: str) -> bool:
        return any(m.id == model for m in self.models)


IMAGE_PROVIDERS: tuple[ImageProvider, ...] = (
    ImageProvider(
        "cloudflare",
        "Cloudflare Workers AI",
        "gratis · 10.000 neuronas al día",
        (
            KeyField("CLOUDFLARE_ACCOUNT_ID", "ID de cuenta", secret=False),
            KeyField("CLOUDFLARE_API_TOKEN", "Token de API"),
        ),
        "CLOUDFLARE_IMAGE_MODEL",
        (
            # Cupos calculados con la tabla de precios de Cloudflare para una
            # imagen de 864x1536: son orientativos, no una promesa.
            ImageModel("@cf/black-forest-labs/flux-2-klein-4b", "FLUX.2 klein 4B", "unas 75 imágenes al día gratis"),
            ImageModel("@cf/black-forest-labs/flux-2-klein-9b", "FLUX.2 klein 9B", "más detalle · unas 7 al día gratis"),
        ),
    ),
    ImageProvider(
        "google",
        "Google Nano Banana",
        "de pago · requiere facturación en Gemini",
        # La misma clave que usa el redactor de Google.
        (KeyField("GEMINI_API_KEY", "Clave de API"),),
        "GEMINI_IMAGE_MODEL",
        (
            ImageModel("gemini-nano-banana-2.1", "Nano Banana 2.1", "≈ 0,05 $ por imagen"),
            ImageModel("gemini-3.1-flash-lite-image", "Nano Banana 2 Lite", "≈ 0,03 $ por imagen"),
            ImageModel("gemini-3-pro-image", "Nano Banana Pro", "≈ 0,13 $ por imagen · más calidad"),
        ),
    ),
)

_BY_ID = {p.id: p for p in IMAGE_PROVIDERS}


def image_provider_by_id(provider_id: str | None) -> ImageProvider | None:
    return _BY_ID.get((provider_id or "").strip().lower())


_MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    #: Con punto: «.jpg», «.png».
    extension: str

    @property
    def media_type(self) -> str:
        return _MEDIA_TYPES.get(self.extension, "image/jpeg")


# --------------------------------------------------------------------------- #
# Trocear el guion
# --------------------------------------------------------------------------- #

# Corta después de un cierre de frase. El signo de apertura español («¿», «¡»)
# va con la frase siguiente, así que no hace falta tratarlo aparte.
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


@dataclass(frozen=True)
class Beat:
    """Un tramo del guion que pide su propia imagen."""

    #: Segundo en el que entra, estimado con el mismo ritmo que la duración.
    start: float
    text: str

    def as_dict(self) -> dict:
        return {"start": self.start, "text": self.text}


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]


def plan_cuts(
    sentences: Sequence[str],
    seconds_per_scene: float = SECONDS_PER_SCENE,
    max_scenes: int = MAX_SCENES,
) -> list[int]:
    """
    Dónde empieza cada escena si se reparte solo por longitud: el índice de su
    primera frase. Escenas de unos `seconds_per_scene` segundos sin partir
    ninguna frase: cada frase cae en la escena donde queda su mitad. Así una
    frase larga no se corta en dos imágenes y las cortas se agrupan.

    No sabe de qué habla cada frase: puede juntar en una imagen el final de
    una idea y el principio de la siguiente. El guion visual corta por sentido
    (`domain.storyboard`) y usa esto solo para recortar si el modelo se pasa.
    """
    if not sentences:
        return []
    lengths = [len(s.split()) for s in sentences]
    total = sum(lengths)
    wanted = round(total / WORDS_PER_SECOND / seconds_per_scene)
    count = max(1, min(max_scenes, wanted, len(sentences)))
    per_scene = total / count

    cuts: list[int] = []
    last_slot = None
    words_before = 0
    for index, length in enumerate(lengths):
        slot = min(count - 1, int((words_before + length / 2) // per_scene))
        if slot != last_slot:
            cuts.append(index)
            last_slot = slot
        words_before += length
    return cuts


def beats_from_cuts(sentences: Sequence[str], cuts: Sequence[int]) -> list[Beat]:
    """
    Las escenas que empiezan en esas frases (índices crecientes, el primero 0),
    cada una hasta la frase anterior a la siguiente y con su segundo estimado.
    """
    bounds = [*cuts, len(sentences)]
    beats: list[Beat] = []
    for first, end in zip(bounds, bounds[1:]):
        words_before = sum(len(s.split()) for s in sentences[:first])
        start = 0.0 if not beats else round(words_before / WORDS_PER_SECOND, 1)
        beats.append(Beat(start, " ".join(sentences[first:end])))
    return beats


def plan_beats(
    script: str | None,
    seconds_per_scene: float = SECONDS_PER_SCENE,
    max_scenes: int = MAX_SCENES,
) -> list[Beat]:
    """El guion repartido en escenas solo por longitud (`plan_cuts`)."""
    sentences = split_sentences(clean_script(script))
    return beats_from_cuts(sentences, plan_cuts(sentences, seconds_per_scene, max_scenes))


# --------------------------------------------------------------------------- #
# Qué se le pide a cada imagen
# --------------------------------------------------------------------------- #

#: Topes de lo que acompaña a cada encargo. Holgados para editar a mano, y
#: aun así el encargo entero queda por debajo de las 300 palabras.
LOOK_LIMIT = 800
NAME_LIMIT = 40
TRAITS_LIMIT = 600
MAX_CHARACTERS = 6

#: Imágenes de referencia por escena: Cloudflare acepta de `input_image_0` a
#: `input_image_3`. Si una escena nombra más elementos guardados, los primeros.
MAX_REFERENCES = 4

#: Qué es cada elemento que se repite. Solo cambia cómo se pinta su imagen de
#: referencia (`domain.saved_characters`): un retrato, una foto de producto…
KINDS = ("persona", "animal", "objeto", "lugar")
DEFAULT_KIND = "persona"

#: Un fotograma de película no lleva rótulos; un cartel o una imagen de redes,
#: sí. Probado con la misma semilla: «Jesús envía a sus discípulos desde el
#: monte» salía con el versículo escrito en el cielo, y con esto delante, limpia.
MEDIUM = "Fotograma de película"

#: Los subtítulos del motor ocupan una banda que empieza a mitad de pantalla
#: (CAPTION_Y_RATIO = 0,52 en el generador): lo importante va por encima.
FRAMING = "Imagen vertical, con el motivo principal y las caras en la mitad superior del encuadre."


@dataclass(frozen=True)
class Character:
    """
    Algo que sale en varias escenas con los rasgos que no cambian: una persona,
    un animal, un objeto (una máquina, un juguete, un juego) o un lugar.
    """

    name: str
    #: Edad, cara, pelo, ropa con sus colores; o forma, materiales y colores.
    #: Se repite tal cual en cada imagen.
    traits: str
    kind: str = DEFAULT_KIND
    #: Id en la biblioteca si viene de ahí: su imagen de referencia acompaña a
    #: cada escena donde sale, para que se vea igual de un video a otro.
    saved: int | None = None

    def as_dict(self) -> dict:
        return {"name": self.name, "traits": self.traits, "kind": self.kind, "saved": self.saved}


@dataclass(frozen=True)
class VisualGuide:
    """
    Lo que comparten todas las imágenes de un video para parecer del mismo.

    El generador pinta cada escena por separado y sin ver las demás: si cada
    una se describe a su aire, sale un personaje distinto en cada imagen. Con
    el mismo estilo, los mismos rasgos repetidos palabra por palabra y la misma
    semilla, las escenas casan.
    """

    look: str = ""
    characters: tuple[Character, ...] = ()
    #: Misma semilla, mismo «pulso» del generador. None: la que él quiera.
    seed: int | None = None

    def as_dict(self) -> dict:
        return {
            "look": self.look,
            "characters": [c.as_dict() for c in self.characters],
            "seed": self.seed,
        }


def fold(text: str) -> str:
    """Minúsculas y sin tildes, para comparar nombres como los escribe cualquiera."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(plain.lower().split())


def cast_in(description: str, characters: tuple[Character, ...]) -> tuple[Character, ...]:
    """Los personajes que nombra la descripción: solo esos llevan sus rasgos al encargo."""
    plain = fold(description)
    return tuple(c for c in characters if re.search(rf"\b{re.escape(fold(c.name))}\b", plain))


def as_sentence(text: str) -> str:
    text = " ".join(text.split()).rstrip(" .")
    return f"{text}." if text else ""


_ORDINALS = ("primera", "segunda", "tercera", "cuarta")


def reference_line(referenced: Sequence[Character], first: int = 0) -> str:
    """
    Qué imagen de referencia es de quién, por orden de llegada. `first` es la
    posición de la primera de estas: al corregir una imagen, la primera
    referencia es la propia imagen y las de la biblioteca van detrás.

    Con ordinales y no con números: la documentación de FLUX.2 [klein] no dice
    si la primera referencia es la «imagen 0» o la «imagen 1», y con dos
    elementos en la escena equivocarse cruzaría las caras.
    """
    if len(referenced) == 1 and first == 0:
        who = f"{referenced[0].name} se ve igual que en la imagen de referencia"
    else:
        parts = [f"{c.name} se ve igual que en la {_ORDINALS[first]} imagen de referencia" if i == 0
                 else f"{c.name}, que en la {_ORDINALS[first + i]}" for i, c in enumerate(referenced)]
        who = "; ".join(parts)
    return f"{who}: mismo aspecto (cara, pelo, ropa, forma y colores), en la postura y el lugar que pide la escena."


def image_prompt(
    description: str,
    guide: VisualGuide | None = None,
    referenced: Sequence[Character] = (),
    framing: str = FRAMING,
) -> str:
    """
    El encargo completo para el generador, en el orden que pide FLUX.2: primero
    qué se ve, después quién es cada elemento que sale, de qué imagen de
    referencia sale cada uno, el estilo y el encuadre.

    Nada de citas ni de prohibiciones. FLUX.2 no admite «prompts negativos»: un
    «sin texto» no quita letras, y una frase entre comillas la escribe tal cual.
    Contra las letras funciona decir qué es la imagen: un fotograma (MEDIUM).
    """
    guide = guide or VisualGuide()
    lines = [f"{MEDIUM}: {as_sentence(description)}"]
    lines += [f"{c.name}: {as_sentence(c.traits)}" for c in cast_in(description, guide.characters)]
    if referenced:
        lines.append(reference_line(referenced[:MAX_REFERENCES]))
    lines.append(f"Estilo: {as_sentence(guide.look or DEFAULT_STYLE)}")
    lines.append(framing)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Corregir una imagen ya pintada
# --------------------------------------------------------------------------- #

#: Tope de lo que el usuario cuenta que está mal. Una o dos frases bastan.
CORRECTION_LIMIT = 500

#: Lo que no se toca al corregir: si no se dice, el generador aprovecha para
#: repintar la escena entera y el arreglo se lleva lo que estaba bien.
KEEP_THE_REST = (
    "Deja todo lo demás como está: el encuadre, las personas y su ropa, el fondo, "
    "la luz, los colores y el estilo."
)


def correction_prompt(
    correction: str,
    description: str = "",
    guide: VisualGuide | None = None,
    referenced: Sequence[Character] = (),
) -> str:
    """
    El encargo para corregir una imagen: la imagen va como primera referencia
    y el generador la edita en vez de pintar otra desde cero.

    El fallo va tal como lo escribe el usuario («la mujer tiene seis dedos»,
    «quita las letras del cielo») detrás de qué hacer con él: FLUX.2 y Nano
    Banana editan siguiendo instrucciones, y «corrige» lo es. Los rasgos de
    quien sale y las referencias de la biblioteca van como en `image_prompt`,
    para que el arreglo no le cambie la cara a nadie. Ni estilo ni encuadre:
    ya están en la imagen, y repetirlos invita a repintarla.
    """
    guide = guide or VisualGuide()
    lines = [
        f"Corrige la primera imagen de referencia. Lo que hay que arreglar: {as_sentence(correction)}",
        KEEP_THE_REST,
    ]
    if description:
        lines.append(f"La escena muestra: {as_sentence(description)}")
    lines += [f"{c.name}: {as_sentence(c.traits)}" for c in cast_in(f"{description} {correction}", guide.characters)]
    if referenced:
        lines.append(reference_line(referenced[: MAX_REFERENCES - 1], first=1))
    return "\n".join(lines)


def validate_correction(correction: str | None) -> str:
    text = " ".join((correction or "").split())
    if not text:
        raise ValidationError("Cuenta qué está mal en la imagen para que la IA lo corrija.")
    if len(text) > CORRECTION_LIMIT:
        raise ValidationError(
            f"La corrección es demasiado larga: déjala por debajo de {CORRECTION_LIMIT} caracteres."
        )
    return text


def validate_guide(look: str | None, characters: list[Mapping] | None, seed: int | None) -> VisualGuide:
    """La guía que acompaña a un encargo, tal como llega de la interfaz."""
    look = " ".join((look or "").split())
    if len(look) > LOOK_LIMIT:
        raise ValidationError(f"El estilo es demasiado largo: déjalo por debajo de {LOOK_LIMIT} caracteres.")

    cast: list[Character] = []
    for item in characters or []:
        character = validate_character(item)
        if character is None:
            continue
        if any(fold(c.name) == fold(character.name) for c in cast):
            raise ValidationError(f"Hay dos elementos llamados «{character.name}».")
        cast.append(character)
    if len(cast) > MAX_CHARACTERS:
        raise ValidationError(f"Como mucho {MAX_CHARACTERS} personajes o elementos por video.")

    if seed is not None and not 0 <= seed < 2**32:
        raise ValidationError("La semilla tiene que ser un entero positivo de 32 bits.")
    return VisualGuide(look, tuple(cast), seed)


def validate_character(item: Mapping) -> Character | None:
    """Un elemento tal como llega de la interfaz. Una fila vacía es None, no un error."""
    name = " ".join(str(item.get("name") or "").split())
    traits = " ".join(str(item.get("traits") or "").split())
    if not name and not traits:
        return None
    if not name or not traits:
        raise ValidationError("Cada personaje o elemento necesita un nombre y sus rasgos.")
    if len(name) > NAME_LIMIT or len(traits) > TRAITS_LIMIT:
        raise ValidationError(
            f"«{name[:NAME_LIMIT]}» es demasiado largo: nombre hasta {NAME_LIMIT} caracteres "
            f"y rasgos hasta {TRAITS_LIMIT}."
        )
    kind = str(item.get("kind") or DEFAULT_KIND).strip().lower()
    if kind not in KINDS:
        raise ValidationError(f"«{name}» tiene un tipo desconocido: {kind}. Vale {', '.join(KINDS)}.")
    saved = item.get("saved")
    if saved is not None and (isinstance(saved, bool) or not isinstance(saved, int) or saved < 1):
        raise ValidationError(f"«{name}» trae una referencia a la biblioteca que no vale.")
    return Character(name, traits, kind, saved)


def new_illustration_key() -> str:
    return f"im-{uuid4().hex[:10]}"


def illustration_name(topic: str, job_key: str, extension: str) -> str:
    """
    «ia-finanzas_3735928559.jpg». El sufijo numérico sale de la clave del
    trabajo, así que la galería agrupa las imágenes de un tema y repetir el
    mismo encargo sobrescribe el mismo archivo en vez de duplicarlo.
    """
    digits = int(job_key.rsplit("-", 1)[-1][:8] or "0", 16)
    # Sin tildes antes de `slugify`, que las descarta: «Café» daría «caf».
    return f"ia-{slugify(fold(topic))[:40]}_{digits}{extension}"


def validate_description(description: str | None, required: bool = True) -> str:
    """`required=False` al corregir: una imagen puesta a mano desde la galería no trae descripción."""
    text = " ".join((description or "").split())
    if not text:
        if not required:
            return ""
        raise ValidationError("Describe qué debe mostrar la imagen.")
    if len(text) > 1500:
        raise ValidationError("La descripción es demasiado larga: déjala por debajo de 1.500 caracteres.")
    return text
