"""
Transiciones: cómo se pasa de un plano al siguiente.

Hasta ahora todo cambio era un corte seco, tanto de una escena a la siguiente
como, dentro de una imagen fija, de un encuadre al siguiente (`domain.motion`).
Ahora el usuario elige cómo entra cada escena —o una para todo el video— y
cuánto dura. La escena usa esa misma transición para sus cambios de encuadre.

Una transición se centra en el corte: empieza `seconds / 2` antes y acaba
`seconds / 2` después. Así la escena sigue entrando cuando la voz dice su
palabra (`scene.synced_to_voice`): a mitad del cambio ya domina la nueva.

Aquí se decide cuándo cambia y cómo se ve cada plano en cada instante. Pintar
los fotogramas es de `infrastructure.transitions`. Las mismas opciones viven
en `web/domain/transition.ts`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from app.domain.errors import ValidationError

CUT = "corte"
CROSSFADE = "fundido"
DIP = "negro"
SLIDE = "deslizar"
ZOOM = "zoom"

KINDS = (CUT, CROSSFADE, DIP, SLIDE, ZOOM)

#: Medio segundo se ve como transición sin frenar el ritmo de un reel.
DEFAULT_SECONDS = 0.5
MIN_SECONDS = 0.2
MAX_SECONDS = 1.5

#: Cuánto se acerca el zoom de entrada en el punto más cerrado: un 30 %.
ZOOM_DEPTH = 0.3


@dataclass(frozen=True)
class Transition:
    kind: str = CUT
    seconds: float = DEFAULT_SECONDS

    def as_dict(self) -> dict:
        return asdict(self)


def validate_transition(data: Mapping | Transition | None) -> Transition:
    """La que llega de la interfaz. Sin nada, el corte seco de siempre."""
    if isinstance(data, Transition):
        data = data.as_dict()
    data = data or {}
    kind = str(data.get("kind") or CUT).strip().lower()
    if kind not in KINDS:
        raise ValidationError(f"Transición desconocida: «{kind}». Usa {', '.join(KINDS)}.")
    seconds = data.get("seconds", DEFAULT_SECONDS)
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not MIN_SECONDS <= seconds <= MAX_SECONDS:
        raise ValidationError("Una transición dura entre 0,2 y 1,5 segundos.")
    return Transition(kind, float(seconds))


def read_transition(data: object) -> Transition | None:
    """La guardada con un video o una escena; None si no hay o ya no vale."""
    if not isinstance(data, Mapping):
        return None
    try:
        return validate_transition(data)
    except ValidationError:
        return None


# --------------------------------------------------------------------------- #
# Cuándo cambia
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Change:
    """El paso de un plano al siguiente: en qué segundo cae el corte y cómo se pasa."""

    at: float
    kind: str = CUT
    #: Cuánto dura la transición; cero en un corte seco.
    seconds: float = 0.0

    @property
    def start(self) -> float:
        return self.at - self.seconds / 2

    @property
    def end(self) -> float:
        return self.at + self.seconds / 2


def plan_changes(bounds: Sequence[float], entries: Sequence[Transition]) -> list[Change]:
    """
    Los cambios entre planos consecutivos. `bounds` son los límites de los
    planos, del principio del primero al final del último (n + 1 valores para
    n planos), y `entries[i]` es cómo entra el plano i + 1.

    Una transición nunca dura más que ninguno de los dos planos que une: así
    dos seguidas no se pisan aunque una escena dure medio segundo.
    """
    changes: list[Change] = []
    for i, transition in enumerate(entries):
        at = bounds[i + 1]
        if transition.kind == CUT:
            changes.append(Change(at))
            continue
        room = min(at - bounds[i], bounds[i + 2] - at)
        changes.append(Change(at, transition.kind, max(0.0, min(transition.seconds, room))))
    return changes


def reach(bounds: Sequence[float], changes: Sequence[Change]) -> list[tuple[float, float]]:
    """
    Desde y hasta qué segundo hay que pintar cada plano: su tramo más la mitad
    de las transiciones de los lados, que es cuando se ve junto al vecino.
    """
    last = len(bounds) - 2
    return [
        (changes[i - 1].start if i > 0 else bounds[0], changes[i].end if i < last else bounds[-1])
        for i in range(last + 1)
    ]


@dataclass(frozen=True)
class Blend:
    """A mitad de un cambio."""

    kind: str
    #: De 0 (todo el plano que sale) a 1 (todo el que entra), lineal en el tiempo.
    progress: float


def moment(changes: Sequence[Change], t: float) -> tuple[int, Blend | None]:
    """
    Qué plano se ve en el segundo `t` y, si está cambiando, la mezcla con el
    siguiente. Un corte seco no tiene duración: nunca hay mezcla.
    """
    for i, change in enumerate(changes):
        if t < change.start:
            return i, None
        if t < change.end:
            return i, Blend(change.kind, (t - change.start) / change.seconds)
    return len(changes), None


# --------------------------------------------------------------------------- #
# Cómo se ve
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Look:
    """Cómo se ve cada plano en un instante del cambio."""

    #: Opacidad del plano que entra, encima del que sale.
    alpha: float = 0.0
    #: Brillo de cada uno, de 0 a 1: el fundido a negro los apaga.
    gain_out: float = 1.0
    gain_in: float = 1.0
    #: Escala de cada uno sobre su centro: el zoom de entrada.
    zoom_out: float = 1.0
    zoom_in: float = 1.0
    #: Fracción del ancho que ocupa ya el que entra por la derecha empujando
    #: al otro; None si no se desliza.
    push: float | None = None


def smooth(p: float) -> float:
    """Arranca y frena suave: un movimiento a velocidad fija se ve mecánico."""
    p = min(max(p, 0.0), 1.0)
    return p * p * (3 - 2 * p)


def look(blend: Blend) -> Look:
    p = min(max(blend.progress, 0.0), 1.0)
    if blend.kind == CROSSFADE:
        return Look(alpha=p)
    if blend.kind == DIP:
        # Baja a negro en la primera mitad y sube con el nuevo en la segunda.
        if p < 0.5:
            return Look(alpha=0.0, gain_out=1 - 2 * p)
        return Look(alpha=1.0, gain_in=2 * p - 1)
    if blend.kind == SLIDE:
        return Look(alpha=1.0, push=smooth(p))
    if blend.kind == ZOOM:
        # El que sale se acerca deprisa y el que entra llega ya cerca y se
        # abre; se funden en el tramo central, cuando los dos van muy cerrados.
        e = smooth(p)
        return Look(
            alpha=smooth((p - 0.3) / 0.4),
            zoom_out=1 + ZOOM_DEPTH * e,
            zoom_in=1 + ZOOM_DEPTH * (1 - e),
        )
    return Look(alpha=1.0 if p >= 0.5 else 0.0)
