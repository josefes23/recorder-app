"""
La galería de fondos: listar, subir, buscar en el catálogo de stock, bajar lo
que el usuario marcó y servir miniaturas.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path, PurePath
from typing import BinaryIO

from app.application.ports import BackgroundStore, StockLibrary
from app.domain.background import Background, extension_of, is_supported
from app.domain.errors import DomainError, EngineError, NotFoundError, ValidationError
from app.domain.stock import StockClip, clip_name


@dataclass
class DownloadReport:
    """Cómo acabó una descarga: qué entró, qué ya estaba y qué falló."""

    added: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)
    #: «nombre: motivo», uno por clip que no se pudo bajar.
    failed: list[str] = field(default_factory=list)


class BackgroundUseCases:
    def __init__(self, store: BackgroundStore, stock: StockLibrary) -> None:
        self._store = store
        self._stock = stock

    def list(self) -> list[Background]:
        return self._store.list()

    def upload(self, filename: str | None, stream: BinaryIO) -> tuple[str, list[Background]]:
        if not is_supported(filename):
            raise ValidationError(f"Formato no admitido: {extension_of(filename) or 'sin extensión'}")
        name = self._store.save(PurePath(filename or "").name, stream)
        return name, self._store.list()

    def search(self, query: str) -> list[StockClip]:
        """Clips del catálogo para la búsqueda, señalando los que ya están en la galería."""
        query = query.strip()
        if not query:
            raise ValidationError("Escribe qué clips buscar.")
        clips = []
        for clip in self._stock.search(query):
            name = clip_name(query, clip.id)
            clips.append(replace(clip, name=name, owned=self._store.has(name)))
        return clips

    def download(self, query: str, ids: list[int]) -> tuple[DownloadReport, list[Background]]:
        """
        Baja a la galería los clips marcados de una búsqueda. Cada uno se vuelve
        a pedir al catálogo por su id: la interfaz manda ids, no URLs.
        """
        query = query.strip()
        if not query:
            raise ValidationError("Falta la búsqueda a la que pertenecen los clips.")
        if not ids:
            raise ValidationError("Marca al menos un clip para descargar.")

        report = DownloadReport()
        first_failure: str | None = None
        for clip_id in dict.fromkeys(ids):  # sin repetidos, en el orden en que se marcaron
            name = clip_name(query, clip_id)
            if self._store.has(name):
                report.existing.append(name)
                continue
            try:
                with self._stock.open(self._stock.clip(clip_id)) as stream:
                    self._store.save(name, stream)
            except DomainError as exc:
                report.failed.append(f"{name}: {exc}")
                first_failure = first_failure or str(exc)
                continue
            report.added.append(name)

        if not report.added and first_failure:
            # Si no entró ninguno, lo que hay que enseñar es el motivo: sin
            # clave, sin red… y no una lista de fallos iguales.
            raise EngineError(first_failure)
        return report, self._store.list()

    def file(self, name: str) -> Path:
        """El fondo entero, para verlo a tamaño grande."""
        path = self._store.path(name)
        if path is None:
            raise NotFoundError("Ese fondo ya no está en la galería.")
        return path

    def delete(self, name: str) -> list[Background]:
        """Quita un fondo de la galería, archivo incluido."""
        if self._store.path(name) is None:
            raise NotFoundError("Ese fondo ya no está en la galería.")
        self._store.remove(name)
        return self._store.list()

    def thumbnail(self, thumb: str) -> Path:
        path = self._store.thumbnail_path(thumb)
        if path is None:
            raise NotFoundError("Miniatura no encontrada.")
        return path
