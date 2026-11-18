"""
El asistente de crecimiento: ganchos, retención, títulos, SEO, puntaje y tendencias.

Lo mismo que hace un vidIQ, pero con el modelo del guion y sobre lo que hay en
el estudio. Cada consejo es un encargo al modelo con una respuesta en JSON que
aquí se valida y se limpia: la interfaz nunca ve algo que no tenga la forma
esperada.

Una limitación que la interfaz enseña: el modelo no consulta datos en vivo de
ninguna plataforma. Sus «tendencias» y puntajes son criterio de un redactor
que conoce cómo funcionan los Shorts, Reels y TikTok, no estadísticas.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from app.domain.errors import ValidationError, WriterError
from app.domain.writer import strip_reasoning

#: Más que esto de cada lista es relleno.
MAX_ITEMS = 8
TEXT_LIMIT = 600

_COMMON = """Responde solo con un objeto JSON, sin markdown ni comentarios, todo en español.
Sé concreto y honesto: no halagues. Si algo está flojo, dilo y di cómo arreglarlo.
No inventes cifras de búsquedas, visitas ni estadísticas: no tienes acceso a datos en vivo."""

HOOKS_PROMPT = f"""Eres un guionista especializado en retener a la audiencia de videos cortos verticales (YouTube Shorts, TikTok, Reels). Tu trabajo: el gancho, lo que se dice o se ve en los primeros tres segundos y decide si la gente se queda o desliza.

Propón cinco ganchos distintos para el video que te describen, cada uno de un tipo diferente: pregunta, dato sorprendente, promesa, contradicción o historia. Cada gancho:
- Es una frase hablada de como mucho veinte palabras, que se pueda decir de un tirón.
- Casa con lo que el video cuenta de verdad: nada de clickbait que el guion no cumple.
- Se puede poner como primera frase del guion sin cambiar el resto.

{_COMMON}
Formato: {{"hooks": [{{"text": "la frase", "type": "pregunta|dato|promesa|contradicción|historia", "why": "por qué retiene, en una frase"}}]}}"""

RETENTION_PROMPT = f"""Eres un analista de retención de videos cortos verticales. Lees el guion de un video y dices dónde la gente se va a ir y qué cambiar para que se quede hasta el final.

Mira, por este orden: el gancho (primera frase), el ritmo (frases largas, tramos sin novedad, explicaciones antes de tiempo), los giros que renuevan el interés, y el cierre (una llamada a la acción clara, o un final que invita a verlo otra vez).

Da un puntaje de retención de 0 a 100 y entre tres y seis problemas concretos. Cada uno cita la frase o el tramo afectado, explica el problema y propone una solución que se pueda aplicar ya.

{_COMMON}
Formato: {{"score": 0, "summary": "veredicto en una frase", "issues": [{{"at": "frase o tramo, citado", "problem": "...", "fix": "..."}}], "keep": ["lo que funciona y no hay que tocar"]}}"""

TITLES_PROMPT = f"""Eres especialista en títulos para videos cortos (YouTube Shorts, TikTok, Reels). Propones títulos que se entienden en un segundo, despiertan curiosidad y llevan la búsqueda principal del tema.

Propón seis títulos distintos para el video. Cada uno:
- De como mucho sesenta caracteres, sin emojis ni mayúsculas gritadas.
- Fiel al guion: lo que promete, el video lo cumple.
- Con una nota de 0 a 100 según claridad, curiosidad y palabra clave, y el motivo en una frase.

Ordénalos de mayor a menor nota. Si ya hay un título, puntúalo también (entra en la lista con su texto exacto) para poder compararlo.

{_COMMON}
Formato: {{"titles": [{{"text": "el título", "score": 0, "why": "por qué"}}]}}"""

SEO_PROMPT = f"""Eres especialista en SEO para videos cortos: lo que leen los buscadores de YouTube, TikTok e Instagram para decidir a quién enseñárselo.

Evalúa la descripción actual del video (puede estar vacía) y propón una mejor. Da un puntaje de 0 a 100 de la actual y señala qué mejorar. La propuesta:
- Empieza por las dos o tres búsquedas que alguien escribiría para encontrar el video, dichas con naturalidad.
- Sigue con un resumen fiel de dos o tres frases y termina con tres a cinco hashtags en minúsculas.
- Entre 300 y 600 caracteres, sin emojis ni markdown.
Añade de cinco a diez etiquetas (palabras clave) para el campo de etiquetas.

{_COMMON}
Formato: {{"score": 0, "tips": ["qué mejorar de la actual"], "improved": "la descripción propuesta", "tags": ["etiqueta"]}}"""

SCORE_PROMPT = f"""Eres un consultor de crecimiento para creadores de videos cortos verticales. Recibes un video completo (tema, título, guion y descripción) y lo puntúas con criterio, como lo haría un buen editor.

Puntúa de 0 a 100 estas partes y el total: gancho, ritmo, claridad, título y descripción. Solo puntúa las que tengan material: si falta el título o la descripción, no las incluyas. Para cada una, una nota de una frase. Después, las tres acciones que más subirían el resultado, de mayor a menor impacto, escritas como instrucciones concretas.

{_COMMON}
Formato: {{"total": 0, "parts": [{{"name": "gancho", "score": 0, "note": "..."}}], "actions": ["..."]}}"""

TRENDS_PROMPT = f"""Eres un estratega de contenido para videos cortos verticales. Te dan un tema o un nicho y propones qué contar a continuación.

Primero, cinco ideas de video nuevas dentro del nicho: cada una con un título provisional, el ángulo que la diferencia de lo que ya hace todo el mundo, por qué funcionaría y un gancho para empezarla. Después, de tres a cinco tendencias del nicho que, por lo que sabes, están funcionando: formatos, temas o estructuras.

Importante: no tienes datos en vivo. Todo lo que dices sale de lo que sabes sobre cómo funcionan estas plataformas; dilo en una nota breve, sin disculparte.

{_COMMON}
Formato: {{"ideas": [{{"title": "...", "angle": "...", "why": "...", "hook": "..."}}], "trends": [{{"topic": "...", "why": "..."}}], "note": "aviso sobre los datos"}}"""


@dataclass(frozen=True)
class Kind:
    id: str
    name: str
    prompt: str
    #: Sin guion no tiene sentido (retención, puntaje, SEO) o basta el tema.
    needs_script: bool
    parse: Callable[[dict], dict]


# Validación de la respuesta ------------------------------------------------- #


def _text(value: object, limit: int = TEXT_LIMIT) -> str:
    return " ".join(str(value or "").split())[:limit]


def _score(value: object) -> int:
    try:
        number = round(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, number))


def _items(value: object, keep: Callable[[dict], dict | None]) -> list[dict]:
    if not isinstance(value, list):
        return []
    out = [item for raw in value if isinstance(raw, dict) and (item := keep(raw))]
    return out[:MAX_ITEMS]


def _strings(value: object, limit: int = TEXT_LIMIT) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for raw in value if (text := _text(raw, limit))][:MAX_ITEMS]


def _hooks(data: dict) -> dict:
    hooks = _items(
        data.get("hooks"),
        lambda h: {"text": _text(h.get("text")), "type": _text(h.get("type"), 30).lower(), "why": _text(h.get("why"))}
        if _text(h.get("text"))
        else None,
    )
    if not hooks:
        raise WriterError("El modelo no propuso ningún gancho. Vuelve a intentarlo.")
    return {"hooks": hooks}


def _retention(data: dict) -> dict:
    issues = _items(
        data.get("issues"),
        lambda i: {"at": _text(i.get("at")), "problem": _text(i.get("problem")), "fix": _text(i.get("fix"))}
        if _text(i.get("problem"))
        else None,
    )
    summary = _text(data.get("summary"))
    if not issues and not summary:
        raise WriterError("El análisis llegó vacío. Vuelve a intentarlo.")
    return {"score": _score(data.get("score")), "summary": summary, "issues": issues, "keep": _strings(data.get("keep"))}


def _titles(data: dict) -> dict:
    titles = _items(
        data.get("titles"),
        lambda t: {"text": _text(t.get("text"), 120), "score": _score(t.get("score")), "why": _text(t.get("why"))}
        if _text(t.get("text"))
        else None,
    )
    if not titles:
        raise WriterError("El modelo no propuso ningún título. Vuelve a intentarlo.")
    return {"titles": sorted(titles, key=lambda t: -t["score"])}


def _seo(data: dict) -> dict:
    improved = "\n".join(" ".join(line.split()) for line in str(data.get("improved") or "").splitlines()).strip()
    if not improved:
        raise WriterError("El modelo no propuso una descripción. Vuelve a intentarlo.")
    tags = [t.lstrip("#").lower() for t in _strings(data.get("tags"), 40)]
    return {"score": _score(data.get("score")), "tips": _strings(data.get("tips")), "improved": improved[:5000], "tags": tags}


def _score_video(data: dict) -> dict:
    parts = _items(
        data.get("parts"),
        lambda p: {"name": _text(p.get("name"), 40).lower(), "score": _score(p.get("score")), "note": _text(p.get("note"))}
        if _text(p.get("name"))
        else None,
    )
    if not parts:
        raise WriterError("El puntaje llegó vacío. Vuelve a intentarlo.")
    return {"total": _score(data.get("total")), "parts": parts, "actions": _strings(data.get("actions"))}


def _trends(data: dict) -> dict:
    ideas = _items(
        data.get("ideas"),
        lambda i: {
            "title": _text(i.get("title"), 120),
            "angle": _text(i.get("angle")),
            "why": _text(i.get("why")),
            "hook": _text(i.get("hook")),
        }
        if _text(i.get("title"))
        else None,
    )
    trends = _items(
        data.get("trends"),
        lambda t: {"topic": _text(t.get("topic"), 120), "why": _text(t.get("why"))} if _text(t.get("topic")) else None,
    )
    if not ideas and not trends:
        raise WriterError("El modelo no propuso ideas. Vuelve a intentarlo.")
    return {"ideas": ideas, "trends": trends, "note": _text(data.get("note"))}


KINDS: tuple[Kind, ...] = (
    Kind("hooks", "Ganchos", HOOKS_PROMPT, False, _hooks),
    Kind("retention", "Retención", RETENTION_PROMPT, True, _retention),
    Kind("titles", "Títulos", TITLES_PROMPT, False, _titles),
    Kind("seo", "SEO de la descripción", SEO_PROMPT, True, _seo),
    Kind("score", "Puntaje del video", SCORE_PROMPT, True, _score_video),
    Kind("trends", "Tendencias e ideas", TRENDS_PROMPT, False, _trends),
)
BY_ID = {kind.id: kind for kind in KINDS}

#: El id del prompt editable de cada consejo (`domain.prompts`).
def prompt_id(kind: Kind | str) -> str:
    return f"growth_{kind.id if isinstance(kind, Kind) else kind}"


def kind_by_id(kind_id: str | None) -> Kind:
    found = BY_ID.get((kind_id or "").strip().lower())
    if found is None:
        raise ValidationError(f"No existe ese consejo: «{kind_id}».")
    return found


# El encargo ---------------------------------------------------------------- #


def check_inputs(kind: Kind, topic: str, script: str) -> None:
    """Rechaza el encargo si no hay de qué hablar."""
    if kind.needs_script and not script.strip():
        raise ValidationError("Escribe primero el guion: este consejo lo analiza.")
    if not kind.needs_script and not (topic.strip() or script.strip()):
        raise ValidationError("Escribe un tema o el guion para poder aconsejarte.")


def build_growth_prompt(topic: str, script: str = "", title: str = "", description: str = "", length: str = "") -> str:
    """Lo que se sabe del video, como mensaje del usuario."""
    lines = [f"Tema: {topic.strip() or 'sin tema'}"]
    if length.strip():
        lines.append(f"Duración objetivo: {length.strip()}")
    if title.strip():
        lines.append(f"Título actual: {title.strip()}")
    prompt = "\n".join(lines)
    if script.strip():
        prompt += f"\n\nGuion del video:\n{script.strip()}"
    if description.strip():
        prompt += f"\n\nDescripción actual:\n{description.strip()}"
    return prompt


def _json_object(raw: str | None) -> dict:
    text = strip_reasoning(raw).strip()
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start : end + 1]) if 0 <= start < end else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        raise WriterError("La respuesta del modelo no se pudo leer. Vuelve a intentarlo, o cambia de modelo en «Modelo del guion».")
    return data


def parse_growth(kind: Kind, raw: str | None) -> dict:
    """Lee la respuesta del modelo y la deja con la forma que espera la interfaz."""
    return kind.parse(_json_object(raw))
