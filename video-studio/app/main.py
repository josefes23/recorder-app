"""API local de video-studio. Se abre en localhost; no está pensada para exponerse.

Arranque: `uvicorn app.main:app`. Aquí solo se construye la raíz de composición
real y se monta la app sobre ella (`app/api/factory.py`); las rutas están en
`app/api/routes` y la lógica en `app/application`.

Importar este módulo abre y migra `data/studio.db`: las pruebas no lo importan.
"""

from __future__ import annotations

from app.api.factory import create_app
from app.container import build_container

app = create_app(build_container())
