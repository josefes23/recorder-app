"""Cuerpos de las peticiones. Son el contrato con `web/infrastructure/http-gateway.ts`."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.voice import DEFAULT_PITCH, DEFAULT_RATE, DEFAULT_VOICE


class ScriptRequest(BaseModel):
    topic: str
    notes: str = ""


class WriterRequest(BaseModel):
    provider: str
    api_key: str = ""
    model: str = ""


class SceneIn(BaseModel):
    background: str | None = None
    start: float = 0.0


class PreviewRequest(BaseModel):
    caption: str = ""
    topic: str = ""
    background: str | None = None
    style: dict = Field(default_factory=dict)


class RenderRequest(BaseModel):
    topic: str
    script: str
    voice: str = DEFAULT_VOICE
    rate: str = DEFAULT_RATE
    pitch: str = DEFAULT_PITCH
    style: dict = Field(default_factory=dict)
    scenes: list[SceneIn] = Field(default_factory=list)


class DownloadRequest(BaseModel):
    """Los clips marcados de una búsqueda: la búsqueda da nombre a los archivos."""

    query: str
    ids: list[int] = Field(default_factory=list)
