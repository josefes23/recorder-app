"""
El acabado de un video: lo que se le hace una vez armado para que suene y se
vea mejor. Cuatro cosas, todas opcionales y todas apagadas por defecto:

- Audio: limpiar la voz (ruido, graves, presencia) y llevar el volumen final a
  un nivel parejo (-14 LUFS, el de YouTube, Instagram y TikTok).
- Color: un «look» y tres ajustes (exposición, contraste, saturación), solo
  sobre el fondo: los subtítulos no se tiñen.
- Ritmo: recortar las pausas largas de la voz. Las palabras se re-sincronizan,
  así que subtítulos y escenas siguen cayendo donde deben.
- Tarjetas: una de entrada con el título y una de cierre con una llamada a la
  acción.

Reglas puras; el trabajo con ffmpeg, moviepy y Pillow vive en
`app/infrastructure/finish.py`. Las mismas opciones viven en `web/domain/finish.ts`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field

from app.domain.errors import ValidationError

#: El volumen al que se lleva la mezcla final, en LUFS, y su techo de pico.
TARGET_LUFS = -14.0
TRUE_PEAK_DB = -1.5

#: Los «looks» de color. `none` no toca el color.
LOOKS: tuple[tuple[str, str], ...] = (
    ("none", "Natural"),
    ("warm", "Cálido"),
    ("cool", "Frío"),
    ("cine", "Cine"),
    ("vivid", "Vivo"),
    ("mono", "Blanco y negro"),
)
LOOK_IDS = frozenset(look for look, _ in LOOKS)

#: Cada ajuste de color va de -1 a 1; 0 no cambia nada.
ADJUST_LIMIT = 1.0

#: Una pausa más larga que esto (segundos) se acorta hasta `KEEP_GAP`.
MAX_GAP = 0.45
KEEP_GAP = 0.25
#: Silencio al final: más de esto se recorta hasta `KEEP_TAIL`.
MAX_TAIL = 0.7
KEEP_TAIL = 0.35

#: Cuánto dura cada tarjeta, en segundos.
INTRO_SECONDS = 1.6
OUTRO_SECONDS = 2.6
INTRO_LIMIT = 90
OUTRO_LIMIT = 120


@dataclass(frozen=True)
class AudioFinish:
    #: Quitar ruido y graves de la voz, igualar su volumen y darle presencia.
    clean: bool = False
    #: Llevar la mezcla final (voz y música) a `TARGET_LUFS`.
    normalize: bool = False


@dataclass(frozen=True)
class ColorFinish:
    look: str = "none"
    exposure: float = 0.0
    contrast: float = 0.0
    saturation: float = 0.0

    @property
    def active(self) -> bool:
        return self.look != "none" or any((self.exposure, self.contrast, self.saturation))


@dataclass(frozen=True)
class PaceFinish:
    #: Acortar las pausas largas de la voz.
    tighten: bool = False


@dataclass(frozen=True)
class CardsFinish:
    #: Texto de la tarjeta de entrada (admite *resaltado*); vacío = sin tarjeta.
    intro: str = ""
    #: Texto de la tarjeta de cierre; vacío = sin tarjeta.
    outro: str = ""


@dataclass(frozen=True)
class Finish:
    audio: AudioFinish = field(default_factory=AudioFinish)
    color: ColorFinish = field(default_factory=ColorFinish)
    pace: PaceFinish = field(default_factory=PaceFinish)
    cards: CardsFinish = field(default_factory=CardsFinish)

    @property
    def active(self) -> bool:
        return bool(
            self.audio.clean or self.audio.normalize or self.color.active or self.pace.tighten
            or self.cards.intro or self.cards.outro
        )

    def as_dict(self) -> dict:
        return asdict(self)


# Validación ---------------------------------------------------------------- #


def _section(data: Mapping, key: str) -> Mapping:
    value = data.get(key)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValidationError(f"Los ajustes de «{key}» del acabado llegaron con un formato que no se entiende.")
    return value


def _adjust(value: object, name: str) -> float:
    if value in (None, ""):
        return 0.0
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValidationError(f"«{name}» tiene que ser un número entre -1 y 1.") from None
    if number != number:  # NaN
        raise ValidationError(f"«{name}» tiene que ser un número entre -1 y 1.")
    return round(max(-ADJUST_LIMIT, min(ADJUST_LIMIT, number)), 2)


def _line(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def validate_finish(data: Mapping | None) -> Finish:
    """Los ajustes de acabado que llegan de la interfaz, comprobados uno a uno."""
    if data is None:
        return Finish()
    if not isinstance(data, Mapping):
        raise ValidationError("Los ajustes del acabado llegaron con un formato que no se entiende.")
    audio, color, pace, cards = (_section(data, key) for key in ("audio", "color", "pace", "cards"))
    look = str(color.get("look") or "none")
    if look not in LOOK_IDS:
        raise ValidationError(f"Look de color desconocido: «{look}». Usa {', '.join(sorted(LOOK_IDS))}.")
    return Finish(
        audio=AudioFinish(clean=bool(audio.get("clean")), normalize=bool(audio.get("normalize"))),
        color=ColorFinish(
            look=look,
            exposure=_adjust(color.get("exposure"), "Exposición"),
            contrast=_adjust(color.get("contrast"), "Contraste"),
            saturation=_adjust(color.get("saturation"), "Saturación"),
        ),
        pace=PaceFinish(tighten=bool(pace.get("tighten"))),
        cards=CardsFinish(intro=_line(cards.get("intro"), INTRO_LIMIT), outro=_line(cards.get("outro"), OUTRO_LIMIT)),
    )


def read_finish(data: Mapping | None) -> Finish:
    """Como `validate_finish`, pero para lo ya guardado: lo que no vale se ignora en vez de fallar."""
    try:
        return validate_finish(data)
    except ValidationError:
        return Finish()


# Ritmo: recortar pausas ---------------------------------------------------- #


@dataclass(frozen=True)
class TightenPlan:
    #: Los tramos de la voz original que se conservan, en orden: (desde, hasta) en segundos.
    keep: list[tuple[float, float]]
    #: Las palabras con sus tiempos en la voz ya recortada.
    words: list[dict]
    #: Lo que dura la voz recortada.
    duration: float
    #: Cuánto silencio se quitó, en segundos.
    removed: float

    @property
    def changed(self) -> bool:
        return self.removed > 0.0


def tighten_plan(words: Sequence[Mapping], duration: float) -> TightenPlan:
    """
    Qué recortar de la voz para quitar las pausas largas. Una pausa de más de
    `MAX_GAP` entre dos palabras se deja en `KEEP_GAP`, repartida a los dos
    lados; el silencio final se acorta igual. Las marcas de cada palabra se
    corren lo que se quitó antes de ellas: subtítulos y escenas, que salen de
    esas marcas, siguen cuadrando.
    """
    marks = sorted(
        ({"text": str(w["text"]), "start": float(w["start"]), "end": float(w["end"])} for w in words),
        key=lambda w: w["start"],
    )
    if not marks or duration <= 0:
        return TightenPlan([(0.0, max(duration, 0.0))], [dict(w) for w in marks], max(duration, 0.0), 0.0)

    cuts: list[tuple[float, float]] = []
    half = KEEP_GAP / 2
    for before, after in zip(marks, marks[1:]):
        gap = after["start"] - before["end"]
        if gap > MAX_GAP:
            cuts.append((before["end"] + half, after["start"] - half))
    tail = duration - marks[-1]["end"]
    if tail > MAX_TAIL:
        cuts.append((marks[-1]["end"] + KEEP_TAIL, duration))

    keep: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in cuts:
        keep.append((cursor, start))
        cursor = end
    keep.append((cursor, duration))
    keep = [(a, b) for a, b in keep if b - a > 1e-6]

    def moved(t: float) -> float:
        return t - sum(min(max(t - start, 0.0), end - start) for start, end in cuts)

    removed = sum(end - start for start, end in cuts)
    shifted = [{**w, "start": round(moved(w["start"]), 4), "end": round(moved(w["end"]), 4)} for w in marks]
    return TightenPlan(keep, shifted, round(duration - removed, 4), round(removed, 4))
