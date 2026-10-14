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
| ffmpeg | `brew install ffmpeg` | `winget install Gyan.FFmpeg` | `sudo apt install ffmpeg` |

> **Mac:** alcanza con el `ffmpeg` común. No trae libass, así que el grabador
> dibuja los subtítulos con Pillow y salen igual. Si ya tenés `ffmpeg-full`
> (con libass), lo encuentra y lo usa solo; no vale la pena instalarlo: no
> tiene binario precompilado y se compila durante horas.
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
| `DEMO_EMAIL` / `DEMO_PASSWORD` | La cuenta **demo** del equipo en staging (pedísela a quien administra el repo). Nunca una cuenta real. |
| `APP_URL` | La URL de staging, donde está la liga demo. Para probar contra tu máquina, `http://localhost:5173` (si tu base tiene los mismos datos). |
| `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` *(opcional)* | Voz oficial para grabar finales en tu máquina. Normalmente los finales los graba el workflow. |
| `APP_DIR` *(opcional)* | Carpeta del código de la PWA, si lo tenés. Claude lo lee para escribir escenas más precisas. |
| `APP_DEV_CMD` *(opcional)* | Con `APP_DIR`, por ejemplo `npm run dev`: el grabador levanta la app solo. |

Probá con la app de ejemplo incluida:

```bash
uv run grabar.py --config ejemplo/config.py
```

Los videos quedan en `salida/ejemplo/crear_tarea/`.

---

## Uso con un asistente (recomendado)

Abrí esta carpeta en VS Code y pedile la funcionalidad a tu asistente. Mira la
app (leyendo el código o inspeccionando la pantalla), escribe la escena con la
narración, la graba, revisa los cuadros y te entrega los videos.

| Asistente | Cómo pedirlo |
|---|---|
| **Claude Code** | `/grabar-demo configurar una cancha nueva` |
| **Codex** | `grabá un demo de cómo configurar una cancha nueva` |
| **Copilot** (modo agente) | `/grabar-demo configurar una cancha nueva` |

Los tres siguen el mismo instructivo. VS Code te sugiere instalar sus
extensiones al abrir la carpeta.

Para arreglar un video ya grabado, contale qué viste mal:
`/corregir-demo en el alta de liga faltó cargar los jugadores desde un Excel`
(en Codex, "corregí el demo de …"). Cambia solo lo necesario, regraba y
revisa cada corrección en los cuadros.

| Archivo | Para qué | Lo usa |
|---|---|---|
| `AGENTS.md` | Reglas del proyecto | Codex, Copilot y Claude Code (vía `CLAUDE.md`) |
| `.claude/skills/grabar-demo/SKILL.md` | El paso a paso para grabar un demo | Los tres |
| `.claude/skills/corregir-demo/SKILL.md` | El paso a paso para corregir un demo ya grabado | Los tres |
| `.claude/settings.json` | Permisos; impide leer `.env` | Claude Code |
| `.codex/rules/grabar.rules` | Permite correr el grabador sin preguntar | Codex (con el proyecto marcado como confiable) |
| `.vscode/settings.json` | Permite correr el grabador sin preguntar | Copilot |

Si cambiás el flujo, editá el `SKILL.md`: vale para los tres.

## Uso manual

```bash
uv run grabar.py                          # todas las escenas, celular + escritorio
uv run grabar.py configurar_cancha        # una escena (o varias)
uv run grabar.py --perfil mobile          # solo celular
uv run grabar.py --listar                 # app configurada y escenas disponibles
uv run grabar.py --inspeccionar /ruta     # elementos de una pantalla y sus selectores
uv run grabar.py --ver                    # navegador visible, para depurar
uv run grabar.py --remezclar              # rehace audio y subtítulos SIN regrabar
uv run grabar.py configurar_cancha --hoja # hoja de cuadros para revisar el video
uv run grabar.py --musica musica/x.mp3    # o --sin-musica
uv run grabar.py --voz es-AR-TomasNeural
uv run grabar.py --voz-prueba             # tono en vez de voz: prueba sin internet
uv run grabar.py --webm                   # además exporta .webm
uv run --extra azure grabar.py --proveedor-voz azure   # voz oficial (finales)
```

Los videos finales no se graban a mano: salen del workflow **Escenas contra
staging** (ver [CONTRIBUTING.md](CONTRIBUTING.md#flujo-para-un-video-nuevo)).

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
| `<escena>-mobile.json` / `-desktop.json` | Con qué se hizo: commit, escena, app, sistema, voz, cuadros por segundo |
| `landing.html` | Fragmento listo para pegar: celular en pantallas chicas, escritorio en grandes |

Resoluciones: celular 780×1688 (+ franja de subtítulos), escritorio 1440×900.

Los datos sensibles (emails, teléfonos, documentos y el nombre de la cuenta)
se blurean solos en la página antes de grabarse, solo el dato y no el texto
que lo rodea; ver `OFUSCAR` en `config.py`.

Los videos llevan siempre placas de intro y cierre con la marca, fundidos al
cambiar de pantalla y subtítulos que resaltan la palabra que se dice. El zoom
aparece solo donde hace falta: zonas con muchos botones juntos u objetivos muy
chicos. Se ajustan (o se apagan) en `ANIMACIONES` y `MARCA` de `config.py`,
y `--remezclar` los rehace sin regrabar: [cómo funciona](docs/como-funciona.md#animaciones).

## Cómo trabajamos en equipo

Ramas, revisión de videos, dónde se suben y qué no tocar sin avisar:
[CONTRIBUTING.md](CONTRIBUTING.md).

## Problemas frecuentes

Primero corré `uv run instalar.py`: revisa casi todo y te dice cómo arreglarlo.

- **El video no tiene sonido en VS Code** → la vista previa de VS Code no
  reproduce audio AAC. Abrilo con QuickTime, VLC o el navegador.
- **`uv` o `ffmpeg` "no se reconoce como comando" (Windows)** → abrí una terminal nueva.
  Si ffmpeg sigue sin aparecer, poné su carpeta `bin` en `FFMPEG_DIR` dentro de `.env`.
- **Chromium no arranca (Linux)** → `uv run playwright install-deps chromium` (pide sudo).
- **`edge-tts no pudo generar la voz`** → sin internet. Probá con `--voz-prueba`.
- **`… no responde`** → la app no está levantada o `APP_URL` está mal en tu `.env`.
- **Timeout esperando un selector** → corré con `--ver` para ver qué pasa, o
  `--inspeccionar` sobre esa pantalla para ver los selectores actuales.
- **`AVISO: pocos cuadros por segundo`** → cerrá apps pesadas o bajá `scale` a 1.5 en el perfil mobile.
- **La app muestra una versión vieja** → `SERVICE_WORKERS = "block"` en config.py.
- **`la ruta … usa {liga}, pero config.login() no lo devolvió`** → la cuenta
  demo no entra a ninguna liga en esa `APP_URL`: revisá que apunte a staging.
- **`falta el SDK de Azure Speech`** → corré con `uv run --extra azure grabar.py …`.

Cómo funciona por dentro: [docs/como-funciona.md](docs/como-funciona.md).
