"""
Monta la app FastAPI sobre una raíz de composición ya construida.

Vive aparte de `app/main.py` a propósito: `main` construye el contenedor real
al importarse —abre `data/studio.db` y la migra—, así que unas pruebas que lo
importaran tocarían la base de verdad, y con ella un servidor que estuviera en
marcha con el código anterior. Las pruebas montan la API desde aquí, sobre
dobles.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.api.errors import install_error_handlers
from app.api.routes import (
    animations,
    backgrounds,
    characters,
    config,
    cover,
    description,
    events,
    illustrations,
    library,
    music,
    render,
    scripts,
    takes,
    web,
    writer,
)

if TYPE_CHECKING:
    from app.container import Container

ROUTERS = (
    config.router,
    writer.router,
    scripts.router,
    events.router,
    backgrounds.router,
    music.router,
    illustrations.router,
    animations.router,
    characters.router,
    render.router,
    library.router,
    cover.router,
    description.router,
    takes.router,
)


def create_app(container: Container) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Los hilos de fondo arrancan con el servidor, no al importar el módulo.
        container.start()
        yield

    app = FastAPI(title="video-studio", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.studio = container.studio
    install_error_handlers(app)
    for router in ROUTERS:
        app.include_router(router)
    web.mount_web(app, container.paths.web_build)
    return app
