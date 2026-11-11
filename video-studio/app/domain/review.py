"""
Control de calidad de cada imagen antes de que entre en el video.

Los generadores fallan de formas que se ven de lejos: una persona con un brazo
de más, dos cuerpos fundidos en uno, una frase inventada escrita en el cielo.
Antes de dar una imagen por buena, el modelo del guion —si ve imágenes— la mira
con la descripción que se pidió. Si encuentra un fallo se repinta con otra
semilla, y entra en el video la primera aprobada o, si ninguna lo es, la de
menos fallos.

Medido con 21 imágenes de la galería, 4 con fallos de anatomía y 3 con letras
inventadas: Claude Sonnet 5.5 cazó 6 de 7 sin falsas alarmas, describiendo bien
cada fallo (tres manos, un brazo de más, cuerpos fundidos). Haiku 5.5 y Llama 4
Scout (Cloudflare) solo vieron las letras: ningún fallo de anatomía. Por eso
revisa el modelo del guion y no uno barato aparte.

Aquí viven el encargo y las reglas; hablar con el modelo es de
`infrastructure.llm`, como con el guion.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.errors import WriterError
from app.domain.writer import strip_reasoning

#: Imágenes que se pintan como mucho por escena: la primera y dos repintadas.
MAX_ATTEMPTS = 3

#: No se empieza otro intento si el encargo lleva más de esto. La interfaz se
#: da por vencida a los cinco minutos (GIVE_UP_MS en job-tracker.ts), contando
#: la cola; un intento —pintar y revisar— cabe de sobra en los dos que quedan.
RETRY_DEADLINE = timedelta(minutes=3)

#: Lo que se enseña de cada revisión: unos pocos fallos en una línea cada uno.
MAX_PROBLEMS = 4
PROBLEM_LIMIT = 200

UNEXPLAINED = "El revisor la rechazó sin decir por qué."

SYSTEM_PROMPT = """Eres el control de calidad de las imágenes de un video vertical para redes. Un modelo de texto a imagen pintó una escena a partir de una descripción; tú la miras antes de que entre en el video y decides si se puede usar.

Recházala solo por fallos que un espectador notaría en el móvil durante los seis segundos que dura la escena:
1. Anatomía imposible: una persona con brazos, manos o piernas de más o de menos; manos o brazos que no salen de ningún cuerpo; cabezas o caras duplicadas o deformes.
2. Cuerpos u objetos fundidos o superpuestos sin sentido: dos personas que se mezclan en una, alguien que atraviesa un objeto, una figura partida o repetida.
3. Letras que no pertenecen a la escena: texto escrito encima de la imagen (títulos, subtítulos, citas, marcas de agua) o palabras inventadas o mal escritas en cualquier parte. Un rótulo bien escrito que encaja en el lugar, como el nombre de un café en su fachada, no es un fallo.
4. Otra escena: no aparece el sujeto principal de la descripción, o la imagen muestra algo completamente distinto.

La descripción es una guía, no una lista que cumplir: un gesto distinto, otra postura, un objeto que falta o sobra o lo que haya dibujado en un papel no son fallos. Tampoco lo son el gusto o el estilo ni los detalles pequeños del fondo que nadie miraría. Que parte de una persona quede fuera del encuadre no es un fallo; una mano o un brazo que no puede ser de nadie de la escena, sí.

Revisa a cada persona por separado: cuenta sus brazos y sus manos y sigue cada uno hasta el hombro del que sale.

Mira bien antes de contestar y responde con un único objeto JSON, sin markdown ni texto antes o después:
{"ok": true, "problems": []}
o bien
{"ok": false, "problems": ["..."]}
Cada problema es una frase corta en español, de menos de quince palabras, que dice qué falla y dónde, por ejemplo: «el hombre del centro tiene cuatro brazos»."""


@dataclass(frozen=True)
class Review:
    """Lo que dijo el revisor de una imagen."""

    ok: bool
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewReport:
    """Lo que la interfaz cuenta debajo de la escena."""

    #: «approved»: la vio y vale · «flagged»: ningún intento quedó limpio ·
    #: «unchecked»: no se pudo revisar y la imagen entra tal cual.
    status: str
    #: Quién revisó, para la interfaz: «Claude», «Google · gemini-3.6-flash».
    reviewer: str
    #: Imágenes pintadas para esta escena.
    attempts: int
    #: Fallos de la imagen que se quedó (solo si es «flagged»).
    problems: tuple[str, ...] = ()
    #: Fallos de las imágenes descartadas por el camino.
    fixed: tuple[str, ...] = ()
    #: Por qué no se pudo revisar (solo si es «unchecked»).
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "reviewer": self.reviewer,
            "attempts": self.attempts,
            "problems": list(self.problems),
            "fixed": list(self.fixed),
            "detail": self.detail,
        }


def review_prompt(description: str) -> str:
    return f"Descripción de la escena: {' '.join(description.split())}"


def _clip(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= PROBLEM_LIMIT else text[:PROBLEM_LIMIT].rsplit(" ", 1)[0] + "…"


def _verdicts(text: str) -> list[dict]:
    """Cada objeto JSON con un «ok» de verdad o mentira que aparezca en el texto, en orden."""
    decoder = json.JSONDecoder()
    found, at = [], text.find("{")
    while at != -1:
        try:
            value, end = decoder.raw_decode(text, at)
        except ValueError:
            at = text.find("{", at + 1)
            continue
        if isinstance(value, dict) and isinstance(value.get("ok"), bool):
            found.append(value)
        at = text.find("{", end)
    return found


def parse_review(raw: str | None) -> Review:
    """
    Lee el veredicto. Una respuesta ilegible es un error, no un aprobado.

    Vale el último: visto con Sonnet 5.5, a veces contesta, se lo repiensa por
    escrito («Revisando de nuevo…») y vuelve a contestar.
    """
    verdicts = _verdicts(strip_reasoning(raw))
    if not verdicts:
        raise WriterError("El revisor no contestó en el formato esperado.")
    data = verdicts[-1]

    problems = tuple(
        _clip(p) for p in (data.get("problems") or []) if isinstance(p, str) and p.strip()
    )[:MAX_PROBLEMS]
    if data["ok"]:
        return Review(True)
    # Un rechazo sin motivo cuenta como rechazo: repintar cuesta una imagen;
    # colar una con fallos, el video.
    return Review(False, problems or (UNEXPLAINED,))


def retry_seed(seed: int | None, attempt: int) -> int | None:
    """
    La semilla de cada intento. Con la misma semilla y el mismo encargo el
    generador repite la imagen casi exacta, así que repintar exige cambiarla.
    Sin semilla, cada intento ya sale distinto.
    """
    return None if seed is None else (seed + attempt) % 2**32


def may_retry(attempts: int, requested_at: datetime, now: datetime) -> bool:
    return attempts < MAX_ATTEMPTS and now - requested_at < RETRY_DEADLINE


def pick(reviews: Sequence[Review]) -> int:
    """La que entra en el video: la aprobada o, si no hay, la de menos fallos (la primera si empatan)."""
    for i, review in enumerate(reviews):
        if review.ok:
            return i
    return min(range(len(reviews)), key=lambda i: len(reviews[i].problems))


def report(reviewer: str, reviews: Sequence[Review]) -> ReviewReport:
    chosen = pick(reviews)
    kept = reviews[chosen]
    if not kept.ok:
        return ReviewReport("flagged", reviewer, len(reviews), problems=kept.problems)
    fixed = [p for i, r in enumerate(reviews) if i != chosen for p in r.problems]
    return ReviewReport("approved", reviewer, len(reviews), fixed=tuple(dict.fromkeys(fixed)))


def unchecked(reviewer: str, attempts: int, detail: str) -> ReviewReport:
    return ReviewReport("unchecked", reviewer, attempts, detail=detail)
