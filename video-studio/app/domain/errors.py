"""Errores con el mensaje ya redactado para el usuario. La API los traduce a HTTP."""


class DomainError(Exception):
    """Fallo esperable: el mensaje se enseña tal cual en la interfaz."""


class ValidationError(DomainError):
    """La petición no vale: falta un dato o viene mal formado."""


class NotFoundError(DomainError):
    """Lo que se pide no existe, o ya no."""


class WriterError(DomainError):
    """El proveedor del guion no pudo redactarlo."""


class IllustratorError(DomainError):
    """El generador de imágenes no pudo pintar la escena."""


class EngineError(DomainError):
    """El motor o una herramienta externa (ffmpeg, un script) falló."""


class FileInUseError(DomainError):
    """No se pudo borrar un archivo: en Windows pasa si otro programa lo tiene abierto."""
