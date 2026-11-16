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


class CoverIn(BaseModel):
    #: Lo que va entre asteriscos sale resaltado.
    title: str = ""
    design: str = "impacto"
    #: Nombre en la galería; vacío pinta el degradado del tema.
    background: str | None = None


class CoverRequest(CoverIn):
    #: Da color al degradado cuando no hay imagen, como en el render.
    topic: str = ""


class TitlesRequest(BaseModel):
    topic: str = ""
    script: str = ""


class DescriptionRequest(BaseModel):
    topic: str = ""
    script: str = ""
    #: El de la portada, con o sin asteriscos: la descripción casa con él.
    title: str = ""


class RenderRequest(BaseModel):
    topic: str
    script: str
    voice: str = DEFAULT_VOICE
    rate: str = DEFAULT_RATE
    pitch: str = DEFAULT_PITCH
    style: dict = Field(default_factory=dict)
    scenes: list[SceneIn] = Field(default_factory=list)
    #: Se guarda con el video para descargarla después.
    cover: CoverIn | None = None
    #: El texto con que se publica; se guarda con el video para copiarlo después.
    description: str = ""


class DownloadRequest(BaseModel):
    """Los clips marcados de una búsqueda: la búsqueda da nombre a los archivos."""

    query: str
    ids: list[int] = Field(default_factory=list)


class ImageSettingsRequest(BaseModel):
    provider: str
    model: str = ""
    #: Variable del .env → valor. Uno vacío conserva el que hubiera.
    values: dict[str, str] = Field(default_factory=dict)


class CharacterIn(BaseModel):
    name: str = ""
    traits: str = ""
    #: persona, animal, objeto o lugar.
    kind: str = "persona"
    #: Id en la biblioteca si viene de ahí: su imagen de referencia acompaña a la escena.
    saved: int | None = None


class StoryboardRequest(BaseModel):
    topic: str = ""
    script: str = ""
    #: El estilo que pide el usuario; el modelo lo concreta.
    style: str = ""
    #: Lo que ya está en el video: el guion visual mantiene lo que encaje.
    characters: list[CharacterIn] = Field(default_factory=list)


class CharacterSave(BaseModel):
    name: str = ""
    traits: str = ""
    kind: str = "persona"
    #: El estilo del video desde el que se guarda: con él se pinta su imagen de referencia.
    look: str = ""
    #: Vacíos: el generador y el modelo guardados.
    provider: str = ""
    model: str = ""


class ReferenceRequest(BaseModel):
    look: str = ""
    provider: str = ""
    model: str = ""


class IllustrationRequest(BaseModel):
    topic: str = ""
    #: Qué debe mostrar la imagen.
    description: str = ""
    #: La guía visual del video: estilo, reparto y semilla comunes a sus escenas.
    look: str = ""
    characters: list[CharacterIn] = Field(default_factory=list)
    seed: int | None = None
    #: Vacíos: los que estén guardados.
    provider: str = ""
    model: str = ""
    #: Que el modelo del guion la revise y la repinte si ve fallos.
    review: bool = True
    #: Para corregir una imagen en vez de pintar otra: cuál (su nombre en la
    #: galería) y qué está mal. Al corregir, la descripción es opcional.
    source: str = ""
    correction: str = ""


class AnimationRequest(BaseModel):
    topic: str = ""
    #: La imagen de la galería que se anima: será el primer fotograma.
    source: str = ""
    #: Cuánto dura el clip, en segundos enteros (3 a 15): lo que dura su tramo.
    seconds: int = 0
    #: Qué pasa en la escena; ayuda al modelo a saber qué debe moverse.
    description: str = ""
    #: La guía visual del video, como en las imágenes.
    look: str = ""
    characters: list[CharacterIn] = Field(default_factory=list)
    seed: int | None = None
