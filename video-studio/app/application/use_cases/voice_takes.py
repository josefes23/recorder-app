"""
Tomas de voz: generar la voz del guion antes de renderizar, para escuchar la
animática con ella y ver en qué segundo cae cada frase, y recuperar la que usó
un video ya hecho.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from app.application.ports import TakeStore, VoiceSynthesizer
from app.domain.errors import NotFoundError
from app.domain.voice_take import VoiceTake, is_take_key, take_key, take_request


class VoiceTakeUseCases:
    def __init__(self, synthesizer: VoiceSynthesizer, takes: TakeStore) -> None:
        self._synthesizer = synthesizer
        self._takes = takes

    def take(
        self, script: str, voice: str, rate: str, pitch: str, voices: Mapping | None = None,
    ) -> VoiceTake:
        """
        La toma de ese guion con esa voz. Si ya se generó (y su audio sigue
        guardado) se devuelve sin volver a sintetizar; si no, se genera y se
        guarda, y el render la usará tal cual.
        """
        request = take_request(script, voice, rate, pitch, voices)
        key = take_key(request)
        found = self._takes.get(key)
        if found is not None and found.audio:
            return found
        audio, words, duration = self._synthesizer.synthesize(request)
        return self._takes.save(key, audio, words, duration)

    def get(self, key: str) -> VoiceTake:
        """Las marcas de una toma: los tiempos reales de un video ya renderizado."""
        found = self._takes.get(key) if is_take_key(key) else None
        if found is None:
            raise NotFoundError("No hay una toma de voz con esa clave.")
        return found

    def audio_of(self, key: str) -> Path:
        path = self._takes.audio(key) if is_take_key(key) else None
        if path is None:
            raise NotFoundError("El audio de esa toma ya no está guardado: genera la voz otra vez.")
        return path
