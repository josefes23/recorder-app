# Creación de contenido

Herramientas para producir videos cortos: reels con voz y subtítulos, y demos
grabadas de la app TuLigaPro. Son tres proyectos que viven juntos en este repo.

| Proyecto | Qué hace | Stack |
|---|---|---|
| [`auto-video-generator/`](auto-video-generator/README.md) | El motor: guion → voz (edge-tts) → subtítulos → render vertical 1080×1920. Se usa con la skill `/make-video`. | Python (`requirements.txt`) |
| [`video-studio/`](video-studio/README.md) | Interfaz web local para el motor: el mismo proceso en un formulario, con vista previa. | FastAPI + Next.js |
| [`app-demo-recorder/`](app-demo-recorder/README.md) | Graba demos de la PWA: navega la app sola, con voz, subtítulos, música y placas de marca, en celular y escritorio. | Python con `uv` |

```
CreacionContenido/
├── auto-video-generator/   ← el motor
├── video-studio/           ← importa auto-video-generator/scripts/generate.py
├── app-demo-recorder/      ← independiente (adapta la voz y los subtítulos del motor)
└── .github/workflows/      ← los workflows del grabador
```

`video-studio` depende de `auto-video-generator` por ruta: busca la carpeta
hermana `../auto-video-generator`, así que las dos tienen que quedar juntas.
`app-demo-recorder` no depende de los otros dos.

## Instalación

```bash
git clone https://github.com/josefes23/recorder-app.git CreacionContenido
cd CreacionContenido
```

Cada proyecto tiene su propio entorno y se instala por separado, desde su
carpeta. Los pasos completos están en su README.

```bash
# Motor
cd auto-video-generator && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt

# Interfaz web (necesita el motor instalado)
cd video-studio && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
npm --prefix web install && ./run.sh        # http://127.0.0.1:8000

# Grabador de demos
cd app-demo-recorder && uv run instalar.py
```

### Windows 11

Los tres andan en Windows. Lo del sistema se instala con `winget` (después,
abrí una terminal nueva para que tome el PATH):

```powershell
winget install Git.Git
winget install Python.Python.3.13
winget install OpenJS.NodeJS.LTS
winget install Gyan.FFmpeg
winget install astral-sh.uv
```

Los comandos cambian en dos cosas: el entorno guarda los ejecutables en
`.venv\Scripts` (no en `.venv/bin`) y `run.sh` es `py run.py`.

```powershell
# Motor
cd auto-video-generator; py -3.13 -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt

# Interfaz web (necesita el motor instalado)
cd video-studio; py -3.13 -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt
npm --prefix web install; py run.py          # http://127.0.0.1:8000

# Grabador de demos
cd app-demo-recorder; uv run instalar.py
```

`.venv` y `node_modules` no se copian entre máquinas: tienen binarios nativos.

Las credenciales van en el `.env` de cada proyecto, que nunca se sube.

## Lo que no va a git

Los videos generados, los fondos descargados (`auto-video-generator/assets/backgrounds/`),
los datos de `video-studio/data/` y los entornos (`.venv`, `node_modules`).
Están en los `.gitignore` de cada proyecto.

## Workflows

Los del grabador corren dentro de `app-demo-recorder/`:

- `prueba.yml`: graba la app de ejemplo en Windows, Linux y Mac en cada
  cambio del grabador.
- `escenas.yml`: graba las escenas reales contra staging (ver
  [CONTRIBUTING del grabador](app-demo-recorder/CONTRIBUTING.md)).

Y uno para el motor y la interfaz:

- `studio.yml`: pruebas del backend y del front de `video-studio`, y el build
  de la interfaz, en Mac y Windows, cada vez que cambia `video-studio/` o
  `auto-video-generator/`.
