# app-demo-recorder

Graba videos de las funcionalidades de nuestra PWA para la landing y las
redes: navega la app sola, con cursor o toques visibles, **voz en español**,
**subtítulos** y **música de fondo**, en **celular y escritorio**.

Cada funcionalidad es una **escena** (un archivo en `escenas/`): se escribe
una vez y se regraba en un minuto cuando cambia la app.

Funciona en **Windows, Linux y Mac**.

---

## Instalación (una vez)

Necesitás tres cosas: **git**, **uv** (maneja Python y las dependencias) y
**ffmpeg** (arma los videos).

| | Mac | Windows | Linux (Ubuntu/Debian) |
|---|---|---|---|
| uv | `brew install uv` | `winget install astral-sh.uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| ffmpeg | `brew install ffmpeg-full` | `winget install Gyan.FFmpeg` | `sudo apt install ffmpeg` |

> **Mac:** tiene que ser `ffmpeg-full`. El `ffmpeg` común de Homebrew no trae
> libass y no puede quemar los subtítulos en el video. No hace falta
> desinstalar el otro: el grabador encuentra `ffmpeg-full` solo.
>
> **Windows:** después de instalar, cerrá y abrí la terminal para que tome
> los comandos nuevos.

Después, en una terminal:

```bash
git clone <url-del-repo> app-demo-recorder
cd app-demo-recorder
uv run instalar.py
```

`instalar.py` descarga Chromium, crea tu `.env` y revisa que todo esté bien.
Completá el `.env` y volvé a correrlo hasta que no marque ningún ✗:

| Variable | Qué poner |
|---|---|
| `DEMO_EMAIL` / `DEMO_PASSWORD` | La cuenta **demo** del equipo (pedísela a quien administra el repo). Nunca una cuenta real. |
| `APP_URL` | Dónde está la app. Si no programás, la URL de pruebas (staging). Si la corrés en tu máquina, `http://localhost:5173`. |
| `APP_DIR` *(opcional)* | Carpeta del código de la PWA, si lo tenés. Claude lo lee para escribir escenas más precisas. |
| `APP_DEV_CMD` *(opcional)* | Con `APP_DIR`, por ejemplo `npm run dev`: el grabador levanta la app solo. |

Probá con la app de ejemplo incluida:

```bash
uv run grabar.py --config ejemplo/config.py
```

Los videos quedan en `salida/ejemplo/crear_tarea/`.

---

## Uso con Claude Code (recomendado)

Abrí Claude Code en esta carpeta y pedí la funcionalidad:

```
/grabar-demo configurar una cancha nueva
```

Claude mira la app, sea leyendo el código o inspeccionando la pantalla. Después
escribe la escena con la narración, la graba, revisa los cuadros y te entrega
los videos.

## Uso manual

```bash
uv run grabar.py                          # todas las escenas, celular + escritorio
uv run grabar.py configurar_cancha        # una escena (o varias)
uv run grabar.py --perfil mobile          # solo celular
uv run grabar.py --listar                 # app configurada y escenas disponibles
uv run grabar.py --inspeccionar /ruta     # elementos de una pantalla y sus selectores
uv run grabar.py --ver                    # navegador visible, para depurar
uv run grabar.py --remezclar              # rehace audio y subtítulos SIN regrabar
uv run grabar.py --musica musica/x.mp3    # o --sin-musica
uv run grabar.py --voz es-AR-TomasNeural
uv run grabar.py --voz-prueba             # tono en vez de voz: prueba sin internet
uv run grabar.py --webm                   # además exporta .webm
```

`--remezclar` rehace la mezcla en segundos: sirve para cambiar la música, los
volúmenes o el estilo de subtítulos. Cambiar el texto o la voz de la narración
sí requiere regrabar, porque cambia la duración de cada frase.

Para escribir una escena a mano: [docs/escribir-escenas.md](docs/escribir-escenas.md).

## Qué sale

En `salida/<escena>/` (no va a git):

| Archivo | Para qué |
|---|---|
| `<escena>-mobile.mp4` / `-desktop.mp4` | Video con voz y música |
| `<escena>-mobile-subs.mp4` / `-desktop-subs.mp4` | Igual, con subtítulos quemados: ideal para redes y autoplay mudo |
| `.vtt` / `.srt` | Subtítulos para `<track>` (accesibles, se activan en el reproductor) |
| `<escena>-transcripcion.txt` | Texto completo: para la landing (SEO, accesibilidad) o el copy del post |
| `.jpg` | Póster (primer cuadro que se ve antes de reproducir) |
| `landing.html` | Fragmento listo para pegar: celular en pantallas chicas, escritorio en grandes |

Resoluciones: celular 780×1688 (+ franja de subtítulos), escritorio 1440×900.

## Cómo trabajamos en equipo

Ramas, revisión de videos, dónde se suben y qué no tocar sin avisar:
[CONTRIBUTING.md](CONTRIBUTING.md).

## Problemas frecuentes

Primero corré `uv run instalar.py`: revisa casi todo y te dice cómo arreglarlo.

- **No salen los `*-subs.mp4`** → tu ffmpeg no tiene libass. Mac: `brew install ffmpeg-full`.
  Windows: `winget install Gyan.FFmpeg`. Linux: el `ffmpeg` de la distribución ya lo trae.
- **`uv` o `ffmpeg` "no se reconoce como comando" (Windows)** → abrí una terminal nueva.
  Si ffmpeg sigue sin aparecer, poné su carpeta `bin` en `FFMPEG_DIR` dentro de `.env`.
- **Chromium no arranca (Linux)** → `uv run playwright install-deps chromium` (pide sudo).
- **`edge-tts no pudo generar la voz`** → sin internet. Probá con `--voz-prueba`.
- **`… no responde`** → la app no está levantada o `APP_URL` está mal en tu `.env`.
- **Timeout esperando un selector** → corré con `--ver` para ver qué pasa, o
  `--inspeccionar` sobre esa pantalla para ver los selectores actuales.
- **`AVISO: pocos cuadros por segundo`** → cerrá apps pesadas o bajá `scale` a 1.5 en el perfil mobile.
- **La app muestra una versión vieja** → `SERVICE_WORKERS = "block"` en config.py.
- **Los subtítulos se ven con otra letra (Linux)** → no tenés Arial:
  `sudo apt install ttf-mscorefonts-installer`.

Cómo funciona por dentro: [docs/como-funciona.md](docs/como-funciona.md).
