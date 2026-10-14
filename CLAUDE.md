# Monorepo de creación de contenido

Tres proyectos independientes en un solo repo (ver README.md). Al trabajar en
uno, seguí las reglas de su carpeta: `app-demo-recorder/CLAUDE.md` y
`AGENTS.md` mandan dentro de `app-demo-recorder/`.

- Cada proyecto tiene su propio entorno. Corré los comandos desde su carpeta:
  - `auto-video-generator/`: `./.venv/bin/python` (nunca el python del sistema).
  - `app-demo-recorder/`: `uv run …`.
  - `video-studio/`: `./run.sh`; el backend importa `../auto-video-generator`.
- No muevas ni renombres `auto-video-generator/`: `video-studio` la busca como
  carpeta hermana.
- `app-demo-recorder` es independiente: no lo hagas depender de los otros dos.
- Los workflows del grabador están en `.github/workflows/` de la raíz y corren
  con `working-directory: app-demo-recorder`. Si agregás uno para otro
  proyecto, filtralo con `paths:` a su carpeta.
- Nunca leas ni subas los `.env`. Los videos, fondos y datos generados no van
  a git.
