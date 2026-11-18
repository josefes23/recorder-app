"""
Plantillas de prompt con variables `{nombre}`.

Los prompts que se mandan a los modelos se montan con datos del video (el tema,
la duración, la descripción de una escena…). Para que se puedan editar sin
tocar el código, cada uno es una plantilla: el texto fijo lo escribe el
usuario y las variables las rellena el programa.

Solo se sustituyen las variables que el programa conoce; cualquier otra llave
(el JSON de ejemplo de un prompt, por ejemplo) se queda tal cual. Y una línea
que es solo una variable sin valor desaparece entera, para que lo opcional
—los rasgos de un personaje, una referencia— no deje huecos.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

_VARIABLE = re.compile(r"\{([a-z][a-z_]*)\}")


def variables_in(template: str) -> list[str]:
    """Los nombres que aparecen como `{nombre}`, sin repetir y en orden."""
    return list(dict.fromkeys(_VARIABLE.findall(template)))


def render(template: str, values: Mapping[str, object]) -> str:
    def fill(match: re.Match[str]) -> str:
        name = match.group(1)
        return str(values[name]) if name in values else match.group(0)

    lines: list[str] = []
    for line in template.split("\n"):
        alone = _VARIABLE.fullmatch(line.strip())
        if alone and alone.group(1) in values and not str(values[alone.group(1)]).strip():
            continue
        lines.append(_VARIABLE.sub(fill, line))
    return "\n".join(lines)
