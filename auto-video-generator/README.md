# auto-video-generator

Generador de Reels/Shorts verticales (1080x1920) con voz en español y subtítulos
sincronizados. La generación de video no necesita ninguna credencial; solo el
descargador opcional de fondos pide una API key gratuita de Pexels.

## Uso desde Claude Code

```
/make-video Los tres hábitos que arruinan tu sueño
```

Claude escribe el guion, lo pasa al script y te devuelve el `.mp4` terminado.

## Uso desde terminal

```bash
cd auto-video-generator
./.venv/bin/python scripts/generate.py --topic "El café y la productividad"
```

Con guion propio:

```bash
./.venv/bin/python scripts/generate.py \
  --topic "Mi tema" \
  --script-file tmp/mi_guion.txt \
  --voice es-ES-ElviraNeural
```

## Cómo funciona

| Paso | Herramienta | Detalle |
|---|---|---|
| 1. Guion | Claude o plantilla local | 85–120 palabras ≈ 30–45 s |
| 2. Voz | `edge-tts` | Voz neuronal, gratis, sin API key. **Requiere internet.** |
| 3. Subtítulos | `edge-tts` WordBoundary + PIL | Marcas de tiempo reales por palabra, repartidas en bloques equilibrados y dibujadas con Pillow |
| 4. Fondo | `moviepy` | Clip de `assets/backgrounds/` recortado a 9:16, o fondo animado con bokeh |
| 5. Render | `moviepy` + `ffmpeg` | H.264 + AAC, 30 fps |

### Sincronía de subtítulos

`edge-tts` devuelve los tiempos de inicio y fin de **cada palabra**, así que los
subtítulos no son un reparto proporcional estimado: van clavados al audio. Como el
servicio entrega las palabras sin puntuación, `attach_punctuation()` recupera los
signos del guion original para poder cortar los bloques en límites de frase.

Cada frase se reparte luego en bloques de tamaño parejo (`_balance()`) en vez de
cortar en cuanto se llega al límite: así ninguna palabra queda sola en pantalla.
Y cada bloque dura hasta que arranca el siguiente, porque las pausas del TTS tras
cada punto dejarían la pantalla sin texto.

### Por qué los subtítulos no usan `TextClip`

Se dibujan con Pillow (`render_caption_image()`) por dos bugs de moviepy 2.2.1:

- `__break_text()` corta la línea en curso usando `last_space`, un índice absoluto
  sobre el texto completo. A partir del segundo salto los índices se desalinean y
  parte las palabras a mitad (`AGOTADO` → `AGOT` / `ADO`).
- Con `method="label"` calcula de menos la altura del texto multilínea con borde,
  y recorta la última línea por abajo.

Midiendo y dibujando con PIL se controlan el wrap y el lienzo exactos.

## Parámetros

| Flag | Por defecto | Descripción |
|---|---|---|
| `--topic` | *(obligatorio)* | Tema del video |
| `--script` / `--script-file` | plantilla local | Guion a narrar |
| `--voice` | `es-MX-DaliaNeural` | Voz de edge-tts |
| `--rate` | `+8%` | Velocidad de habla |
| `--pitch` | `+0Hz` | Tono |
| `--background` | aleatorio | Fondo concreto |
| `--bg-match` | ninguno | Filtra los fondos por nombre, ej. `sleeping` |
| `--font` | Arial Black | `.ttf` de los subtítulos |
| `--output` | `outputs/video_TIMESTAMP.mp4` | Ruta de salida |
| `--no-anim` | off | Desactiva el "pop" de entrada |
| `--keep-audio` | off | Conserva el `.mp3` |
| `--dry-run` | off | Solo imprime el guion |

## Fondos

Suelta clips o imágenes verticales en `assets/backgrounds/`. Se elige uno al azar
y se recorta al centro a 9:16 sin deformar; si el clip es más corto que el audio,
se repite en bucle.

Para que el fondo acompañe al tema en vez de salir al azar, usa `--bg-match`: filtra
por el nombre del archivo, que lleva el slug de la búsqueda con la que se descargó.

```bash
./.venv/bin/python scripts/generate.py --topic "Tu sueño" --bg-match "sleeping"
```

### Varias escenas en un mismo video

Separa los términos por coma y marca con `@segundo` dónde entra cada uno. Así el
fondo cambia al ritmo del guion en vez de repetir un clip los 40 segundos:

```bash
./.venv/bin/python scripts/generate.py \
  --topic "Los tres hábitos que arruinan tu sueño" \
  --script-file tmp/guion.txt \
  --bg-match "sleeping,coffee@7.3,phone@16.4,alarm@25.5"
```

Sin `@` los términos se reparten en tramos iguales. Cada tramo elige un clip
distinto de los que coincidan, evitando repetir el mismo entre segmentos.

Un término también puede ser el ID de un clip concreto (`6598884`), porque el
filtro busca la subcadena en el nombre del archivo — útil para fijar una escena
que ya te gusta y dejar el resto variando.

Con la carpeta vacía se genera un fondo animado: degradado diagonal más partículas
bokeh que ascienden con deriva lateral. La paleta deriva del tema (determinista:
el mismo tema da siempre el mismo color).

### Descargar clips de Pexels

```bash
./.venv/bin/python scripts/fetch_backgrounds.py --query "ocean" --count 5
./.venv/bin/python scripts/fetch_backgrounds.py --query "night city" --list        # solo mirar
./.venv/bin/python scripts/fetch_backgrounds.py --query "rain" --max-size 40   # tope de MB
```

Elige la versión vertical más pequeña que llegue a 1080 de ancho — subir de ahí
solo añade megas, porque el render recorta a 1080x1920 igualmente.

**Necesitas una API key gratuita** de [pexels.com/api](https://www.pexels.com/api/).
Sin ella la API responde 401 en casi todo: solo sirve unos pocos términos comunes
de una palabra (`nature`, `ocean`, `city`, `abstract`…) que tiene cacheados, y deja
de responder tras unas pocas peticiones desde la misma IP.

Guarda la key en un archivo `.env` en la raíz del proyecto (está en `.gitignore`):

```
PEXELS_API_KEY=tu_key_aqui
```

O pásala con `--api-key`. Licencia Pexels: uso gratuito, también comercial, sin
atribución obligatoria.

Alternativas manuales: [Pixabay](https://pixabay.com/videos/),
[Coverr](https://coverr.co/) — descarga y suelta los `.mp4` en la carpeta.

## Ajustes de estilo

Constantes al inicio de `scripts/generate.py`:

```python
MAX_CHARS_PER_CAPTION = 30   # texto por bloque
MAX_WORDS_PER_CAPTION = 5    # palabras por bloque
CAPTION_FONT_SIZE     = 92   # tamaño de letra
MIN_CAPTION_FONT_SIZE = 52   # suelo al autoajustar
MAX_CAPTION_LINES     = 3    # tope de líneas por bloque
CAPTION_STROKE        = 8    # grosor del borde negro
CAPTION_BOX_H         = 400  # alto de la banda de subtítulos
CAPTION_Y_RATIO       = 0.52 # posición vertical (0 arriba, 1 abajo)
```

`CAPTION_Y_RATIO = 0.52` deja libre el tercio inferior, donde Instagram y TikTok
superponen su interfaz.

## Requisitos

- Python 3.9+ (probado en 3.13)
- ffmpeg (`brew install ffmpeg`)
- Conexión a internet para la síntesis de voz

## Reinstalar

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```
