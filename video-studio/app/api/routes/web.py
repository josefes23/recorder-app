"""
La interfaz es Next.js. En desarrollo la sirve `npm run dev` en :3000 (con las
llamadas a /api reescritas hacia aquí); en producción se exporta a web/out y la
servimos nosotros, para que todo quede en un solo proceso y un solo puerto.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles


def mount_web(app: FastAPI, web_build: Path) -> None:
    @app.get("/")
    def index():
        if not web_build.is_dir():
            return PlainTextResponse(
                "La interfaz no está compilada todavía.\n\n"
                "  ./run.sh          la compila y la sirve aquí mismo\n"
                "  ./run.sh --dev    Next con recarga en caliente en :3000\n",
                status_code=503,
            )
        return FileResponse(web_build / "index.html")

    if web_build.is_dir():
        # Va al final a propósito: montado en "/" captura todo lo que no haya
        # coincidido antes, y las rutas /api están declaradas más arriba.
        app.mount("/", StaticFiles(directory=web_build, html=True), name="web")
