"""Puerto `VideoFiles` sobre el disco local."""

from __future__ import annotations

from pathlib import Path

from app.domain.errors import FileInUseError


def unlink(path: Path) -> None:
    """
    Borra el archivo si existe.

    En Windows no se puede borrar un archivo que alguien tiene abierto —un video
    que la interfaz está reproduciendo, por ejemplo— y `unlink` tira
    PermissionError. En vez de un 500, el usuario ve qué pasó y puede reintentar.
    """
    try:
        path.unlink(missing_ok=True)
    except PermissionError as exc:
        raise FileInUseError(
            f"No se pudo borrar {path.name}: está abierto en otro programa o no hay permiso. "
            "Pausá o cerrá el video y probá de nuevo."
        ) from exc


class LocalVideoFiles:
    def exists(self, path: Path) -> bool:
        return path.is_file()

    def remove(self, path: Path) -> None:
        unlink(path)
