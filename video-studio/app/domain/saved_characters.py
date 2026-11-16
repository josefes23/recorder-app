"""
Biblioteca de elementos que se repiten de un video a otro: personas, animales,
objetos (una máquina de dibujos, un juguete, un juego) y lugares.

Los rasgos escritos mantienen la ropa y la forma, pero la cara cambia en cada
imagen. Por eso cada elemento guardado tiene además una imagen de referencia,
pintada una vez al guardarlo, que acompaña a cada escena donde sale. Probado
con FLUX.2 [klein]: con la referencia, la túnica y el manto salieron idénticos
y la cara muy parecida; sin ella, otra ropa y otra cara.

Los elementos entran a mano —un botón «Guardar» en cada uno— y pasan a un
video también a mano, con «Usar en este video». Nada los trae solo: ni el guion
visual ni que un nombre coincida.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.illustration import DEFAULT_STYLE, Character, as_sentence

#: Cómo se pinta la imagen de referencia de cada tipo: lo que identifica al
#: elemento, centrado, sobre un fondo que no distraiga ni se cuele en la escena.
REFERENCE_FRAMING = {
    "persona": "Retrato de estudio de {name}, de la cintura para arriba, de frente y mirando a cámara, "
    "con los brazos relajados, sobre un fondo liso gris claro.",
    "animal": "Foto de referencia de {name}: el animal entero, de cuerpo completo y de costado, "
    "sobre un fondo liso gris claro.",
    "objeto": "Foto de producto de {name}: el objeto entero, centrado, de frente y bien iluminado, "
    "sobre un fondo liso gris claro.",
    "lugar": "Plano general de {name}, sin nadie, que muestra el espacio entero con luz natural.",
}

_REFERENCE_FILE = re.compile(r"^ref-\d+\.(jpg|png|webp)$")


@dataclass(frozen=True)
class SavedCharacter:
    id: int
    name: str
    traits: str
    kind: str
    #: Archivo de su imagen de referencia, o None mientras no la tenga.
    reference: str | None
    created_at: str
    updated_at: str

    def as_character(self) -> Character:
        return Character(self.name, self.traits, self.kind, self.id)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "traits": self.traits,
            "kind": self.kind,
            "reference": self.reference,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def reference_prompt(character: Character, look: str = "") -> str:
    """El encargo de su imagen de referencia, con el estilo del video desde el que se guarda."""
    framing = REFERENCE_FRAMING.get(character.kind, REFERENCE_FRAMING["persona"])
    return "\n".join([
        framing.format(name=character.name),
        f"{character.name}: {as_sentence(character.traits)}",
        f"Estilo: {as_sentence(look or DEFAULT_STYLE)}",
    ])


def reference_description(character: Character) -> str:
    """Lo que el revisor tiene delante al mirar la imagen de referencia."""
    return f"Imagen de referencia de {character.name}, sola sobre un fondo neutro: {character.traits}"


def reference_name(character_id: int, extension: str) -> str:
    return f"ref-{character_id}{extension}"


def is_reference_name(name: str) -> bool:
    """Solo nombres que haya dado `reference_name`: nada de rutas que salgan de la carpeta."""
    return bool(_REFERENCE_FILE.match(name or ""))
