# Monorepo de creación de contenido

Tres proyectos independientes en un solo repo (ver README.md). Al trabajar en
uno, seguí las reglas de su carpeta: `app-demo-recorder/CLAUDE.md` y
`AGENTS.md` mandan dentro de `app-demo-recorder/`; `video-studio/CLAUDE.md`
fija las capas del backend dentro de `video-studio/`.

- Cada proyecto tiene su propio entorno. Corré los comandos desde su carpeta:
  - `auto-video-generator/`: `./.venv/bin/python` (nunca el python del sistema).
  - `app-demo-recorder/`: `uv run …`.
  - `video-studio/`: `./run.sh`; el backend importa `../auto-video-generator`.
- Todo tiene que andar en Mac y en Windows 11. En Windows el entorno está en
  `.venv/Scripts/python` (no `.venv/bin/python`) y `./run.sh` es `py run.py`.
  No agregues lógica que solo corra en bash: va en Python o en un script de
  Node, y las rutas se arman con `pathlib`. Texto entre procesos, en UTF-8.
- No muevas ni renombres `auto-video-generator/`: `video-studio` la busca como
  carpeta hermana.
- `app-demo-recorder` es independiente: no lo hagas depender de los otros dos.
- Los workflows del grabador están en `.github/workflows/` de la raíz y corren
  con `working-directory: app-demo-recorder`. Si agregás uno para otro
  proyecto, filtralo con `paths:` a su carpeta.
- Nunca leas ni subas los `.env`. Los videos, fondos y datos generados no van
  a git.
