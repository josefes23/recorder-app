# Cómo funciona

```
grabar.py → recorder/runner.py
  1. servidor de la app (DevServer)   si APP_DEV_CMD está y la app no responde
  2. Chromium + login fuera de cámara  config.login()
  3. prepare() de la escena            fuera de cámara
  4. captura + run() de la escena      recorder/capture.py + recorder/demo.py
  5. postproducción                    recorder/post.py (ffmpeg)
```

1. **Login fuera de cámara**: cada escena abre un navegador limpio, hace login
   y va a `START` antes de empezar a grabar.
2. **Captura** (`recorder/capture.py`). La grabación nativa de Playwright
   ignora la densidad retina y comprime a ~40 kbps: el texto sale ilegible. Aquí:
   - escritorio → `Page.startScreencast` (hasta 60 cps);
   - celular → `Page.captureScreenshot` en bucle a 2x (15–30 cps según la máquina).

   Cada cuadro llega con su hora real y se reescribe a 30 fps constantes, así
   el reloj del video coincide con el de las narraciones.
3. **Voz** (`recorder/voice.py`): edge-tts con marcas de tiempo por palabra,
   con caché en `.cache/voz/`. La síntesis corre en paralelo mientras la escena avanza.
4. **Subtítulos** (`recorder/subtitles.py`): las marcas por palabra se agrupan
   en bloques parejos (`attach_punctuation` + `_split_sentences` + `_balance`,
   adaptados de auto-video-generator), con la puntuación y los ¿ ¡ del guion.
5. **Mezcla** (`recorder/post.py`): la música baja al 35 % en cada frase con
   rampas suaves (automatización exacta, no un compresor) y se normaliza a −16 LUFS.

La grabación cruda queda en `salida/<escena>/.work/`: por eso `--remezclar`
rehace los pasos 4 y 5 sin volver a grabar.

## Toques durante la captura

Mientras `captureScreenshot` está en vuelo, Chromium remapea un instante las
coordenadas de entrada y un toque cae en otro elemento. Por eso la captura y
las acciones de `d.` comparten un candado (`input_lock`), y las escenas no
deben usar `d.page.click()` dentro de `run()`.

## Multiplataforma

- `uv run` usa el mismo comando y las mismas versiones (`uv.lock`) en los tres sistemas.
- ffmpeg se busca en `FFMPEG_DIR` (si está en `.env`), en el `ffmpeg-full` de
  Homebrew (Mac) y después en el `PATH` (`recorder/ff.py`).
- El servidor de la app se apaga con todos sus procesos hijos: `killpg` en
  Mac/Linux, `taskkill /T` en Windows (`recorder/runner.py`).
- La salida de consola va en UTF-8 aunque Windows use otra página de códigos
  (`recorder/__init__.py`).
- `.github/workflows/prueba.yml` graba la app de ejemplo en los tres sistemas
  en cada PR, con voz de prueba y sin música.

## Ajustes (config.py)

| Qué | Dónde |
|---|---|
| Voz, velocidad, tono | `VOICE` (lista: `uv run edge-tts --list-voices`) |
| Volumen y ducking de la música | `MUSIC` |
| Tamaño y posición de subtítulos | `SUBTITLES` (`placement: "band"` o `"overlay"`) |
| Resolución y dispositivo | `PROFILES` |
| Ritmo de las acciones | `PACE` (1.2 = 20 % más lento) |
| Modo oscuro | `COLOR_SCHEME = "dark"` |
| Color del toque/resaltado | `ACCENT` |
