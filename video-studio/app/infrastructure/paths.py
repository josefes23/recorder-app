"""Dónde está cada cosa en disco."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path
    #: auto-video-generator, que debe ser carpeta hermana. No se modifica.
    generator: Path
    data: Path

    @classmethod
    def default(cls) -> Paths:
        root = Path(__file__).resolve().parents[2]
        return cls(root=root, generator=root.parent / "auto-video-generator", data=root / "data")

    @property
    def database(self) -> Path:
        return self.data / "studio.db"

    @property
    def thumbs(self) -> Path:
        return self.data / "thumbs"

    @property
    def samples(self) -> Path:
        """Las pruebas de voz, aparte de las tomas: probar voces no desaloja el audio de un guion."""
        return self.data / "samples"

    @property
    def takes(self) -> Path:
        """Las tomas de voz: el audio y el segundo de cada palabra."""
        return self.data / "takes"

    @property
    def posters(self) -> Path:
        """Las portadas en pequeño de la biblioteca, una por video."""
        return self.data / "posters"

    @property
    def references(self) -> Path:
        """Imágenes de referencia de la biblioteca de elementos."""
        return self.data / "references"

    @property
    def music(self) -> Path:
        """La galería de música: pistas que sube el usuario."""
        return self.data / "music"

    @property
    def previews(self) -> Path:
        return self.data / "previews"

    @property
    def outputs(self) -> Path:
        return self.data / "outputs"

    @property
    def jobs(self) -> Path:
        return self.data / "jobs"

    @property
    def env_file(self) -> Path:
        return self.root / ".env"

    @property
    def generator_env(self) -> Path:
        """El .env del motor: ahí vive PEXELS_API_KEY, que su propio script ya usa."""
        return self.generator / ".env"

    @property
    def web_build(self) -> Path:
        return self.root / "web" / "out"

    @property
    def backgrounds(self) -> Path:
        return self.generator / "assets" / "backgrounds"
