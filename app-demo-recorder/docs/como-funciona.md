# Cómo funciona

```
grabar.py → recorder/runner.py
  1. servidor de la app (DevServer)   si APP_DEV_CMD está y la app no responde
  2. Chromium + login fuera de cámara  config.login()
  3. prepare() de la escena            fuera de cámara
  4. captura + run() de la escena      recorder/capture.py + recorder/demo.py
  5. cleanup() de la escena            fuera de cámara, aunque run() falle
  6. postproducción                    recorder/animar.py (Pillow) + recorder/post.py (ffmpeg)
```

1. **Login fuera de cámara**: cada escena abre un navegador limpio, hace login
   y va a `START` antes de empezar a grabar. `config.login()` devuelve los
   datos de la sesión (`{"liga": "…"}`) y el grabador completa con ellos las
   rutas: `START = "/league/{liga}/config/venues"` funciona en staging y en la
   base local de cada uno, que tienen IDs distintos.
2. **Captura** (`recorder/capture.py`). La grabación nativa de Playwright
   ignora la densidad retina y comprime a ~40 kbps: el texto sale ilegible. Aquí:
   - escritorio → `Page.startScreencast` (hasta 60 cps);
   - celular → `Page.captureScreenshot` en bucle a 2x (15–30 cps según la máquina).

   Cada cuadro llega con su hora real y se reescribe a 30 fps constantes, así
   el reloj del video coincide con el de las narraciones.
3. **Voz** (`recorder/voice.py`): marcas de tiempo por palabra, con caché en
   `.cache/voz/`. La síntesis corre en paralelo mientras la escena avanza.
   - `edge` (por defecto): edge-tts, gratis. Usa el "leer en voz alta" de Edge,
     que no es un servicio oficial y puede dejar de andar: para borradores.
   - `azure`: Azure AI Speech, las mismas voces por la API oficial, para los
     finales. `uv run --extra azure grabar.py … --proveedor-voz azure`, con
     `AZURE_SPEECH_KEY` y `AZURE_SPEECH_REGION` en `.env`.
4. **Subtítulos** (`recorder/subtitles.py`): las marcas por palabra se agrupan
   en bloques parejos (`attach_punctuation` + `_split_sentences` + `_balance`,
   adaptados de auto-video-generator), con la puntuación y los ¿ ¡ del guion.
5. **Mezcla** (`recorder/post.py`): la música baja al 35 % en cada frase con
   rampas suaves (automatización exacta, no un compresor) y se normaliza a −16 LUFS.

La grabación cruda queda en `salida/<escena>/.work/`: por eso `--remezclar`
rehace los pasos 4 y 5 sin volver a grabar.

Junto a cada video sale `<escena>-<perfil>.json` con qué se hizo: commit del
grabador (con `+cambios` si la escena no estaba commiteada), hash de la
escena, app, sistema, versión de Chromium, voz, música y cuadros por segundo.
El commit también va en los metadatos del `.mp4`.

## Animaciones

`recorder/animar.py` procesa la grabación cuadro por cuadro con Pillow (ffmpeg
solo decodifica y codifica). Todo sale de `.work/`, así que `--remezclar` lo
rehace sin volver a grabar. Se ajusta en `ANIMACIONES` y `MARCA` de `config.py`.

- **Zoom solo donde hace falta.** Cada acción de `d.` (`click`, `type`,
  `highlight`) anota dónde y cuándo ocurre, cuántos controles hay alrededor y
  cuánto ocupa el objetivo (`events` en `timeline.json`). Hay zoom si la zona
  está cargada (al menos `zoom_si.vecinos` controles cerca) o el objetivo es
  muy chico (menos de `zoom_si.area` de la pantalla); un resaltado, solo si es
  chico, porque ya oscurece el resto. En la escena se fuerza con
  `d.click(obj, zoom=True)` o se evita con `zoom=False`. Los movimientos son
  lentos (0,8 s); acciones seguidas comparten el zoom en vez de ir y volver, y
  un zoom que no alcanza a quedarse quieto no se hace. Se aleja antes de un
  desplazamiento o de una acción sin zoom. El recorte es subpíxel: el `zoompan`
  de ffmpeg redondea y la imagen tiembla. Las grabaciones anteriores a esto no
  tienen las acciones anotadas: sin regrabar, no tienen zoom.
- **Transiciones.** Cuando dos cuadros seguidos difieren más que `CORTE`
  (medido: cambiar de pantalla da 0,10–0,72; desplazarse, 0,04–0,07), el
  cuadro anterior se funde con los siguientes. No se agrega tiempo: voz,
  subtítulos y acciones siguen sincronizados.
- **Subtítulos palabra por palabra.** `subtitles.estados()` arma un estado por
  palabra dicha, con esa palabra en `highlight`. Lo dibujan libass o Pillow;
  los `.vtt`/`.srt` siguen siendo por bloque.
- **Intro y cierre, siempre.** Placas con el ícono de `MARCA`, el título de la
  escena (`TITLE`) y la llamada a la acción, fundidas con el primer y el último
  cuadro. Están activas por defecto (los valores por defecto viven en
  `recorder/animar.py`); se apagan poniendo `intro` o `cierre` en 0. La intro
  corre voz, música y subtítulos lo que dura.

## Datos sensibles

`recorder/ofuscar.js` se inyecta en la página después del login y blurea los
datos sensibles **antes de que se capturen**: nunca llegan a la grabación
cruda. Detecta solo emails, teléfonos (8 a 15 cifras; no fechas ni horarios)
y documentos (DNI de 7-8 cifras, CUIT), en el texto y en los campos. También
el nombre y el email de la cuenta con la que se graba, que `config.login()`
toma de la respuesta de `/auth/login`.

En un texto se blurea **solo el dato**: "Hola, ▒▒▒ · Organizador de La
Fortaleza". Usa la API de resaltados de CSS (`CSS.highlights`), que pinta
rangos exactos sin tocar el DOM de React y acompaña scrolls y animaciones: el
tramo queda con el texto transparente y una sombra difusa del mismo tono
(clara u oscura), más fuerte cuanto más grande la letra. Un `MutationObserver`
revisa todo lo que aparece o cambia. Los campos (`input`) y los `selectores`
se blurean enteros. Se ajusta en `OFUSCAR` de `config.py`: `blur`, más
`textos` o `selectores` (ej. `[data-testid=player-dni]`) para lo que no se
detecta solo.

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
- Los subtítulos usan la fuente de `fonts/` (Liberation Sans, mismas medidas
  que Arial), no la del sistema: salen iguales en los tres (Linux no trae Arial).
  Se queman con libass si el ffmpeg lo trae; si no (el de Homebrew, por
  ejemplo), cada bloque se dibuja como imagen con Pillow y se superpone con
  `overlay` (`subtitles.write_images`). Esa versión no tiene el fundido de 120 ms.
- `uv run grabar.py <escena> --hoja` arma las hojas de cuadros con ffmpeg, así
  ningún asistente depende de comandos propios del sistema para revisar.
- Los workflows están en `.github/workflows/` de la raíz del monorepo y corren
  dentro de `app-demo-recorder/`.
- `prueba.yml` graba la app de ejemplo en los tres sistemas en cada PR que
  toque el grabador, con voz de prueba y sin música.
- `escenas.yml` graba las escenas reales contra staging: una
  prueba rápida cada día hábil (avisa si un cambio de la app rompió una
  escena) y, a mano, los videos finales, todos desde el mismo entorno. Por qué:
  [ADR 001](adr/001-entorno-de-grabacion.md).

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
| Zoom, transiciones, subtítulos animados, intro y cierre | `ANIMACIONES` |
| Ícono, colores y textos de las placas | `MARCA` |
| Color de la palabra que se dice | `highlight` en `SUBTITLES["style"]` |
| Qué se blurea (emails, teléfonos, documentos, cuenta, selectores) y cuánto | `OFUSCAR` |
