"""API local de video-studio. Se abre en localhost; no está pensada para exponerse.

Arranque: `uvicorn app.main:app`. Aquí solo se monta la app sobre la raíz de
composición; las rutas están en `app/api/routes` y la lógica en `app/application`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import install_error_handlers
from app.api.routes import (
    backgrounds,
    characters,
    config,
    events,
    illustrations,
    library,
    render,
    scripts,
    web,
    writer,
)
from app.container import Container, build_container

ROUTERS = (
    config.router,
    writer.router,
    scripts.router,
    events.router,
    backgrounds.router,
    illustrations.router,
    characters.router,
    render.router,
    library.router,
)


def create_app(container: Container | None = None) -> FastAPI:
    container = container or build_container()

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


app = create_app()
