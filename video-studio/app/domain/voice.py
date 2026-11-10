"""Voces disponibles y valores por defecto de la locución."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Voice:
    id: str
    label: str


VOICES: tuple[Voice, ...] = (
    Voice("es-MX-DaliaNeural", "Dalia — México ♀"),
    Voice("es-MX-JorgeNeural", "Jorge — México ♂"),
    Voice("es-ES-ElviraNeural", "Elvira — España ♀"),
    Voice("es-ES-AlvaroNeural", "Álvaro — España ♂"),
    Voice("es-ES-XimenaNeural", "Ximena — España ♀"),
    Voice("es-AR-ElenaNeural", "Elena — Argentina ♀"),
    Voice("es-AR-TomasNeural", "Tomás — Argentina ♂"),
    Voice("es-CO-SalomeNeural", "Salomé — Colombia ♀"),
    Voice("es-CO-GonzaloNeural", "Gonzalo — Colombia ♂"),
    Voice("es-CL-CatalinaNeural", "Catalina — Chile ♀"),
    Voice("es-PE-CamilaNeural", "Camila — Perú ♀"),
    Voice("es-US-PalomaNeural", "Paloma — EE.UU. ♀"),
)

DEFAULT_VOICE = "es-MX-DaliaNeural"
DEFAULT_RATE = "+8%"
DEFAULT_PITCH = "+0Hz"
