"""Claves y ajustes del redactor: el entorno del proceso y los `.env`."""

from __future__ import annotations

import os
from collections.abc import Mapping, MutableMapping
from pathlib import Path

#: Archivos del usuario donde también se buscan claves, después de los del proyecto.
HOME_ENV_FILES: tuple[Path, ...] = (Path.home() / ".anthropic.env",)


def merge_env_lines(lines: list[str], values: Mapping[str, str | None]) -> list[str]:
    """Aplica `values` sobre las líneas de un .env respetando el resto. None borra."""
    pending = dict(values)
    out: list[str] = []
    for line in lines:
        name = line.partition("=")[0].strip()
        if name in pending:
            value = pending.pop(name)
            if value is not None:
                out.append(f"{name}={value}")
        else:
            out.append(line)
    out.extend(f"{name}={value}" for name, value in pending.items() if value is not None)
    return out


class EnvCredentials:
    """
    Lee del entorno del proceso y, si no está, de los .env del proyecto.
    Escribe solo en el .env de video-studio y refleja el cambio en el entorno,
    para que surta efecto sin reiniciar el servidor.
    """

    def __init__(
        self,
        env_file: Path,
        extra_files: tuple[Path, ...] = HOME_ENV_FILES,
        environ: MutableMapping[str, str] | None = None,
    ) -> None:
        self._env_file = env_file
        self._files = (env_file, *extra_files)
        self._environ = os.environ if environ is None else environ

    def get(self, name: str) -> str | None:
        if self._environ.get(name):
            return self._environ[name]
        for env_file in self._files:
            if env_file.is_file():
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    key, _, value = line.partition("=")
                    if key.strip() == name:
                        return value.strip().strip("'\"") or None
        return None

    def save(self, values: Mapping[str, str | None]) -> None:
        lines = self._env_file.read_text(encoding="utf-8").splitlines() if self._env_file.is_file() else []
        self._env_file.write_text("\n".join(merge_env_lines(lines, values)) + "\n", encoding="utf-8")
        self._env_file.chmod(0o600)  # guarda claves de API: que no las lea el resto del sistema

        # get() mira primero el entorno del proceso, así que sin esto el servidor
        # seguiría usando el valor con el que arrancó hasta reiniciarlo.
        for name, value in values.items():
            if value is None:
                self._environ.pop(name, None)
            else:
                self._environ[name] = value
