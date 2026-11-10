"""Puerto `VideoFiles` sobre el disco local."""

from __future__ import annotations

from pathlib import Path


class LocalVideoFiles:
    def exists(self, path: Path) -> bool:
        return path.is_file()

    def remove(self, path: Path) -> None:
        path.unlink(missing_ok=True)
