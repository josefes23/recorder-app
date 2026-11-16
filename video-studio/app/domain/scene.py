"""La línea de tiempo de fondos: en qué segundo entra cada uno."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace

from app.domain.script import WORDS_PER_SECOND, clean_script

# Un tramo más corto que esto no aporta nada y rompe la concatenación.
MIN_SPAN_SECONDS = 0.05


@dataclass(frozen=True)
class Scene:
    background: str | None = None
    start: float = 0.0

    @classmethod
    def from_dict(cls, data: dict | None) -> Scene:
        data = data or {}
        return cls(background=data.get("background") or None, start=float(data.get("start") or 0.0))

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Span:
    """Un fondo ocupando un tramo concreto del video."""

    background: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def timeline_spans(scenes: Iterable[Scene], duration: float) -> list[Span]:
    """Convierte las escenas en tramos consecutivos que cubren el video.

    Las escenas sin fondo se ignoran; la primera arranca siempre en cero aunque
    el usuario la haya puesto más tarde; cada tramo dura hasta la siguiente o
    hasta el final del audio. Si no queda ninguna, la lista vacía le dice al
    motor que use su fondo procedural.
    """
    usable = sorted((s for s in scenes if s.background), key=lambda s: s.start)
    spans: list[Span] = []
    for i, scene in enumerate(usable):
        start = 0.0 if i == 0 else scene.start
        end = usable[i + 1].start if i + 1 < len(usable) else duration
        end = min(end, duration)
        if end - start <= MIN_SPAN_SECONDS:
            continue
        spans.append(Span(scene.background or "", start, end))
    return spans


# --------------------------------------------------------------------------- #
# Del segundo estimado al segundo de la voz
# --------------------------------------------------------------------------- #

#: Cuántas palabras del guion puede saltarse la voz sin perder el hilo: el TTS
#: lee «115» como «ciento quince» o no marca un «¿» suelto. La misma ventana
#: que `attach_punctuation` del motor.
ALIGN_WINDOW = 6

_NOT_WORD = re.compile(r"[^\w]", re.UNICODE)

Mark = tuple[float, float]


def _norm(text: str) -> str:
    return _NOT_WORD.sub("", text).lower()


def _voice_marks(tokens: list[str], words: Sequence[Mapping]) -> list[Mark | None]:
    """(inicio, fin) de cada palabra del guion en la voz; None si la voz no la marcó tal cual."""
    keys = [_norm(t) for t in tokens]
    marks: list[Mark | None] = [None] * len(tokens)
    ti = 0
    for word in words:
        target = _norm(str(word.get("text") or ""))
        if not target:
            continue
        j, limit = ti, min(len(keys), ti + ALIGN_WINDOW)
        while j < limit and keys[j] != target:
            j += 1
        if j < limit:
            marks[j] = (float(word["start"]), float(word["end"]))
            ti = j + 1
    return marks


def _cut_before(k: int, marks: list[Mark | None]) -> float | None:
    """
    Segundo en que cambiar de imagen para que la palabra `k` la estrene: en
    mitad del silencio que la precede si la voz marcó las dos palabras de los
    lados. Si no marcó la de antes, al empezar `k`; si no marcó `k` (un número
    leído con otras palabras), al acabar la última que sí marcó.
    """
    after = next((j for j in range(k, len(marks)) if marks[j]), None)
    before = next((i for i in range(k - 1, -1, -1) if marks[i]), None)
    if after == k and before == k - 1:
        return (marks[before][1] + marks[after][0]) / 2  # type: ignore[index]
    if after == k:
        return marks[after][0]  # type: ignore[index]
    if before is not None:
        return marks[before][1]  # type: ignore[index]
    return None if after is None else marks[after][0]  # type: ignore[index]


def synced_to_voice(scenes: Iterable[Scene], script: str | None, words: Sequence[Mapping]) -> list[Scene]:
    """
    Las escenas con el segundo en que la voz llega a su texto.

    Hasta el render no hay voz, así que el estudio coloca las escenas con la
    duración estimada (`script.WORDS_PER_SECOND`): «segundo 14,4» quiere decir
    «cuando la voz llegue a la palabra 39 del guion». Pero la voz no va a ritmo
    fijo: las palabras largas, los números y la pausa de cada punto la
    alargan, y el error se acumula. En «¿Jesus realmente existió?» la voz duró
    58 s frente a 51,5 estimados y desde la tercera escena cada imagen entraba
    de 4 a 7 s antes que su texto: acompañaba a la frase anterior.

    Aquí cada segundo estimado se traduce a la palabra donde cae y se cambia
    por el momento en que la voz la dice (`words`: las marcas del TTS, con
    `text`, `start` y `end`). Vale igual para las escenas del guion visual que
    para las puestas a mano. La primera no se mueve; las que caen después del
    guion conservan su distancia al final de la voz. Sin marcas, nada cambia.
    """
    scenes = list(scenes)
    tokens = clean_script(script).split()
    marks = _voice_marks(tokens, words)
    known = [m for m in marks if m]
    if not known:
        return scenes

    voice_end = known[-1][1]
    estimated_end = len(tokens) / WORDS_PER_SECOND
    synced: list[Scene] = []
    for scene in scenes:
        k = round(scene.start * WORDS_PER_SECOND)
        if k <= 0:
            synced.append(scene)
            continue
        if k >= len(tokens):
            synced.append(replace(scene, start=round(voice_end + scene.start - estimated_end, 2)))
            continue
        cut = _cut_before(k, marks)
        synced.append(scene if cut is None else replace(scene, start=round(cut, 2)))
    return synced
