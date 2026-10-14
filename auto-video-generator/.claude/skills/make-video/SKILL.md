---
name: make-video
description: Genera un Reel/Short vertical (9:16, 1080x1920) con voz en español y subtítulos sincronizados a partir de un tema. Úsala cuando el usuario escriba "/make-video [TEMA]", pida "hazme un video/reel/short sobre X", o quiera convertir una idea en un video corto para Instagram, TikTok o YouTube Shorts.
---

# make-video

Convierte un tema en un video vertical terminado. Tú escribes el guion; `generate.py`
se encarga de la voz, los subtítulos y el render.

**Raíz del proyecto:** `/Users/josejurado/Documents/CreacionContenido/auto-video-generator`
Haz `cd` a esa ruta antes de nada; todos los comandos de abajo son relativos a ella.

**Intérprete:** usa SIEMPRE `./.venv/bin/python` (nunca `python3` del sistema: las
dependencias están en el entorno virtual del proyecto).

## Flujo

### 1. Escribe el guion

Redáctalo tú, no dejes que el script use su plantilla de respaldo. Requisitos:

- **85–120 palabras.** Es el rango que produce 30–45 s con la velocidad por defecto
  (ritmo medido: 2,7 palabras/s con las voces `es-*` a `--rate +8%`).
- **Español natural y hablado.** Se va a *escuchar*, no leer: frases cortas, sin
  subordinadas largas, sin viñetas ni markdown, sin emojis, sin cifras en dígitos
  (escribe "treinta por ciento", no "30%") — el TTS las pronuncia peor y descuadra
  la sincronía de subtítulos.
- **Estructura:** gancho en los primeros 3 segundos → 2 o 3 ideas concretas →
  cierre con llamada a la acción.
- **Puntuación cuidada.** Los cortes de subtítulo se calculan a partir de comas,
  puntos e interrogaciones del guion. Un texto sin puntuar produce bloques que
  cruzan frases y se leen mal.

Guárdalo en `tmp/guion_<slug-del-tema>.txt` con la herramienta Write.

### 2. Consigue un fondo acorde al tema

Un fondo al azar desentona: humo abstracto en un video sobre el sueño no aporta
nada. Traduce el tema a **un término de búsqueda en inglés** (`sleeping bedroom`,
`coffee morning`, `running fitness`, `office work`) y mira si ya hay material:

```bash
ls assets/backgrounds/ | grep -i "<término>"
```

Si no hay coincidencias, descárgalo:

```bash
./.venv/bin/python scripts/fetch_backgrounds.py --query "<término inglés>" --count 4
```

Si falla por falta de API key, dilo y sigue sin `--bg-match`: se usará el fondo
generado con bokeh, que siempre funciona.

### 3. Genera el video

```bash
./.venv/bin/python scripts/generate.py \
  --topic "<TEMA>" \
  --script-file "tmp/guion_<slug>.txt" \
  --bg-match "<palabra del término, ej. sleeping>"
```

`--bg-match` filtra por el nombre del archivo, que lleva el slug de la búsqueda
con la que se descargó. Usa una sola palabra distintiva, no la frase entera.

**Si el guion recorre varias ideas, dale una escena a cada una.** Un solo clip
repetido 40 segundos aburre. Separa los términos por coma con `@segundo`:

```bash
--bg-match "sleeping,coffee@7.3,phone@16.4,alarm@25.5"
```

Para saber en qué segundo entra cada idea, lanza antes el generador y mira los
tiempos de los bloques, o estima a 2,7 palabras/s desde el inicio del guion.
Un término puede ser también el ID de un clip concreto (`6598884`) si quieres
fijar una escena exacta.

**Cuida la coherencia visual.** Clips de la misma paleta: no mezcles un plano en
blanco y negro o de estudio brillante con otro cálido de dormitorio. Si dudas,
extrae un fotograma de cada candidato y compáralos antes de renderizar:

```bash
ffmpeg -y -loglevel error -ss 3 -i assets/backgrounds/<clip>.mp4 -frames:v 1 tmp/cand.png
```

El script imprime cinco pasos (guion → voz → subtítulos → fondo → render) y
termina con la ruta del `.mp4` en `outputs/`. Un video de ~35 s tarda 2–4 min.

### 4. Verifica antes de reportar

No des la tarea por terminada sin comprobar el resultado:

```bash
V=$(ls -t outputs/*.mp4 | head -1)
ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$V"
ffmpeg -y -loglevel error -ss 5 -i "$V" -frames:v 1 tmp/check.png
```

Debe dar `1080,1920`. Lee `tmp/check.png` con Read para confirmar que los
subtítulos se ven legibles y bien colocados. Después informa al usuario de la
ruta final, la duración y el peso.

## Opciones útiles

| Necesidad | Parámetro |
|---|---|
| Otra voz | `--voice es-ES-ElviraNeural` (♀ España), `es-ES-AlvaroNeural` (♂ España), `es-MX-JorgeNeural` (♂ México), `es-AR-ElenaNeural` (♀ Argentina), `es-CO-SalomeNeural` (♀ Colombia) |
| Habla más lenta / rápida | `--rate "-5%"` / `--rate "+15%"` |
| Fondo concreto | `--background assets/backgrounds/mi_clip.mp4` |
| Fondo por tema | `--bg-match "sleeping"` |
| Ver solo el guion | `--dry-run` |
| Conservar el mp3 | `--keep-audio` |

Voz por defecto: `es-MX-DaliaNeural`. Lista completa: `./.venv/bin/edge-tts --list-voices | grep es-`.

## Fondos

Si `assets/backgrounds/` está vacío se genera un fondo animado (degradado + bokeh)
cuya paleta deriva del tema. Funciona, pero metraje real luce mejor. Hay clips en
la carpeta: se elige uno al azar y se recorta a 9:16 automáticamente. Formatos:
`.mp4 .mov .mkv .webm` e imágenes `.jpg .png .webp`.

Para traer clips nuevos acordes al tema:

```bash
./.venv/bin/python scripts/fetch_backgrounds.py --query "ocean" --count 5
```

Requiere `PEXELS_API_KEY` en el archivo `.env` de la raíz. Si no está configurada,
el script falla con instrucciones: no lo intentes repetidamente, dile al usuario
que necesita la key gratuita de pexels.com/api y sigue con el fondo generado.

## Errores frecuentes

- **`ERROR: edge-tts devolvió un audio vacío`** → sin conexión a internet.
  edge-tts necesita red (no API key, pero sí acceso al servicio de Microsoft).
- **`AVISO: fuera del rango ideal 30-45s`** → el guion se fue de largo o de corto.
  Reescríbelo ajustando el número de palabras y vuelve a lanzar.
- **Render muy lento** → normal en 1080x1920. Si el usuario quiere iterar sobre el
  texto, usa `--dry-run` para revisar el guion sin renderizar.
