#!/usr/bin/env python3
"""
Arranca video-studio en Mac, Linux y Windows.

    python run.py           Interfaz compilada + API en un solo proceso → :8000
    python run.py --dev     Next con recarga en caliente → :3000, API → :8000

Lo que venga después (`--port 8001`, `--reload`) va directo a uvicorn. Usa el
Python de `.venv` aunque lo arranques con otro, así que en Windows alcanza con
`py run.py`. Solo usa la biblioteca estándar. En Mac y Linux, `./run.sh` lo llama.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def venv_python() -> Path:
    """El intérprete del entorno: .venv/bin en Mac y Linux, .venv\\Scripts en Windows."""
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def npm_command(*args: str) -> list[str]:
    exe = shutil.which("npm")  # en Windows es npm.cmd: hace falta la ruta completa
    if exe is None:
        sys.exit("No encuentro npm. Instalá Node.js (ver README) y abrí una terminal nueva.")
    return [exe, "--prefix", "web", *args]


def run(cmd: list[str]) -> int:
    """Corre el comando en esta terminal y devuelve su código de salida."""
    process = subprocess.Popen(cmd, cwd=ROOT)
    while True:
        try:
            return process.wait()
        except KeyboardInterrupt:
            # Ctrl+C también le llega al hijo, que está en la misma terminal:
            # se lo deja cerrar solo en vez de matarlo a mitad de camino.
            continue


def hand_over(cmd: list[str]) -> int:
    """Como el `exec` de bash: el comando reemplaza a este proceso donde se puede."""
    if os.name != "nt":
        os.execv(cmd[0], cmd)
    return run(cmd)  # en Windows execv no reemplaza de verdad el proceso


def port(argv: list[str]) -> str:
    """El puerto en que va a escuchar uvicorn: gana el último `--port` que se le pase."""
    value = "8000"
    for i, arg in enumerate(argv):
        if arg == "--port" and i + 1 < len(argv):
            value = argv[i + 1]
        elif arg.startswith("--port="):
            value = arg.split("=", 1)[1]
    return value


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    os.chdir(ROOT)

    if argv[:1] == ["--dev"]:
        print("Interfaz en http://127.0.0.1:3000 · API en http://127.0.0.1:8000", flush=True)
        return hand_over(npm_command("run", "dev"))

    python = venv_python()
    if not python.is_file():
        sys.exit(f"No encuentro {python.relative_to(ROOT)}. Creá el entorno primero (ver README).")

    if not (ROOT / "web" / "out").is_dir():
        print("No hay interfaz compilada todavía. Compilando…", flush=True)
        if (code := run(npm_command("run", "export"))) != 0:
            return code

    print(f"http://127.0.0.1:{port(argv)}", flush=True)
    return hand_over(
        [str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", *argv]
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
