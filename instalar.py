#!/usr/bin/env python3
"""
Prepara y revisa la instalación, en Windows, Linux y Mac:

    uv run instalar.py

1. Descarga el Chromium de Playwright y prueba que arranque.
2. Crea tu .env a partir de .env.example (si no existe).
3. Revisa ffmpeg (y que pueda quemar subtítulos), tu .env y la app.

Se puede correr todas las veces que quieras: también sirve de diagnóstico.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from recorder import utf8_console  # noqa: E402

utf8_console()
try:
    from dotenv import dotenv_values, load_dotenv
    import playwright  # noqa: F401
except ImportError:
    sys.exit("ERROR: ejecutalo con uv, que instala las dependencias:  uv run instalar.py")

problems: list[str] = []


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def warn(msg: str) -> None:
    print(f"  ! {msg}")


def fail(msg: str, fix: str) -> None:
    print(f"  ✗ {msg}\n      → {fix}")
    problems.append(msg)


def check_chromium() -> None:
    print("Chromium (Playwright)")
    r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
    if r.returncode != 0:
        fail("no se pudo descargar Chromium", "revisá tu conexión y volvé a correr instalar.py")
        return
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        ok("Chromium instalado y arranca")
    except Exception as e:
        fix = ("uv run playwright install-deps chromium   (instala librerías del sistema; pide sudo)"
               if sys.platform.startswith("linux") else "volvé a correr instalar.py")
        fail(f"Chromium no arranca: {str(e).splitlines()[0]}", fix)


def check_ffmpeg() -> None:
    print("ffmpeg")
    from recorder import ff
    try:
        path = ff.need("ffmpeg")
        ff.need("ffprobe")
    except SystemExit:
        fail("no está ffmpeg", ff.install_hint())
        return
    ok(f"ffmpeg en {path}")
    if ff.has_filter("ass"):
        ok("puede quemar subtítulos (libass)")
    else:
        fail("este ffmpeg no quema subtítulos: no saldrán los *-subs.mp4", ff.install_hint())


def check_env() -> None:
    print(".env (configuración personal)")
    env, example = ROOT / ".env", ROOT / ".env.example"
    if not env.exists():
        shutil.copy(example, env)
        warn("creé .env a partir de .env.example: completalo con la cuenta demo")
    values = dotenv_values(env)
    placeholders = dotenv_values(example)
    for key in ("DEMO_EMAIL", "DEMO_PASSWORD"):
        v = values.get(key)
        if not v or v == placeholders.get(key):
            fail(f"{key} sin completar", "pedí los datos de la cuenta demo y ponelos en .env")
        else:
            ok(f"{key} completo")

    app_dir = values.get("APP_DIR")
    if app_dir:
        if Path(os.path.expanduser(app_dir)).is_dir():
            ok(f"APP_DIR: {app_dir}")
        else:
            fail(f"APP_DIR no existe: {app_dir}", "corregí la ruta en .env o borrá la línea")
    else:
        warn("sin APP_DIR: Claude va a usar --inspeccionar en vez de leer el código de la app")

    url = values.get("APP_URL") or "http://localhost:5173"
    try:
        urllib.request.urlopen(url, timeout=4)
        ok(f"la app responde en {url}")
    except Exception as e:
        if hasattr(e, "code"):
            ok(f"la app responde en {url}")
        elif values.get("APP_DEV_CMD") and app_dir:
            warn(f"{url} no responde ahora; se va a levantar sola con APP_DEV_CMD al grabar")
        else:
            warn(f"{url} no responde ahora: levantá la app antes de grabar o revisá APP_URL")


def main() -> None:
    load_dotenv(ROOT / ".env")   # por si define FFMPEG_DIR
    print(f"Python {sys.version.split()[0]} · {sys.platform}\n")
    check_chromium()
    check_ffmpeg()
    check_env()
    print()
    if problems:
        sys.exit(f"Hay {len(problems)} problema(s) para resolver (ver ✗ arriba).")
    print("Todo listo. Probá con la app de ejemplo:\n"
          "  uv run grabar.py --config ejemplo/config.py")


if __name__ == "__main__":
    main()
