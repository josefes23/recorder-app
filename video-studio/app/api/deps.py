"""Cómo llega la aplicación a cada ruta: la deja `main.py` en `app.state`."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.application.studio import Studio


def get_studio(request: Request) -> Studio:
    return request.app.state.studio


StudioDep = Annotated[Studio, Depends(get_studio)]
