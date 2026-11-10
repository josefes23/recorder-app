# video-studio

Interfaz local (FastAPI + Next.js exportado) sobre el motor `../auto-video-generator`,
que se importa como librería y no se modifica. Detalles y decisiones en README.md.

## Backend: capas y dirección de dependencias

`api → application → domain`, con `infrastructure` enchufada solo desde
`app/container.py` (raíz de composición) y desde el worker de render.

- `app/domain/`: reglas puras. Sin E/S, sin FastAPI, sin SQLite, sin el motor.
  Si una función necesita un archivo o una red, no va aquí.
- `app/application/`: casos de uso y puertos (`ports.py`, Protocols). Solo
  importa `domain`. Los errores para el usuario se lanzan como `DomainError`
  (`ValidationError`, `NotFoundError`, `WriterError`, `EngineError`).
- `app/infrastructure/`: un adaptador por puerto. Puede importar `domain` y los
  puertos de `application`; nunca `api`.
- `app/api/`: rutas y schemas. Sin reglas de negocio: valida forma, llama a un
  caso de uso, devuelve. `DomainError` → 400 y `NotFoundError` → 404 los mapea
  `api/errors.py`; no hace falta `try/except` en las rutas para eso.
- Los hilos de fondo arrancan en el `lifespan`, no al importar un módulo.

Para añadir un endpoint: caso de uso en `application` (con prueba sobre los
dobles de `tests/fakes.py`), ruta en `api/routes`, y si necesita algo nuevo del
exterior, un puerto en `ports.py` y su adaptador en `infrastructure`.

## Comandos

- Servir: `./run.sh` (o `./run.sh --dev`).
- Pruebas del backend: `./.venv/bin/python -m unittest discover -s tests -t .`
- Pruebas del front: `cd web && npm test` · tipos: `npm run typecheck`.
- El contrato HTTP lo fija `web/infrastructure/http-gateway.ts`; si cambia una
  respuesta, cambia también `tests/test_api.py` y ese adaptador.
