"""Config de la app de ejemplo: hereda todo de ../config.py y cambia lo mínimo."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import *  # noqa: F401,F403,E402

BASE_URL = "http://localhost:5199"
DEV_SERVER = {"cmd": [sys.executable, "-m", "http.server", "5199"], "cwd": str(Path(__file__).parent / "app")}
SCENES_DIR = "escenas"          # relativo a esta carpeta: ejemplo/escenas
OUTPUT_DIR = "salida/ejemplo"


async def login(page, base_url, env):
    await page.goto(base_url + "/#/login")
    await page.evaluate("localStorage.clear()")
    await page.reload()
    await page.get_by_label("Email").fill(env.get("DEMO_EMAIL", "demo@tareitas.app"))
    await page.get_by_label("Contraseña").fill(env.get("DEMO_PASSWORD", "demo1234"))
    await page.get_by_role("button", name="Ingresar").click()
    await page.wait_for_selector("text=Mis tareas")
