---
name: grabar-demo
description: Graba un video demo de una funcionalidad de la PWA del usuario (celular y escritorio) con voz en español, subtítulos y música, para la landing page. Úsala cuando el usuario escriba "/grabar-demo [FUNCIONALIDAD]", pida "grabá/hacé un video de cómo se usa X en mi app", o quiera contenido de demostración para la landing.
---

# grabar-demo

Convierte "mostrá cómo se hace X en la app" en videos terminados. Tú escribes
la escena (acciones + narración); `grabar.py` navega, graba, pone voz,
subtítulos y música.

Trabajas en la raíz del repo (donde está `grabar.py`). El equipo usa Windows,
Linux y Mac: ejecuta SIEMPRE con `uv run` (nunca `.venv/bin/python` ni el
python del sistema) y no uses `/tmp` ni rutas absolutas de nadie.

**No leas `.env`**: tiene las credenciales de la cuenta demo. Lo que necesitas
de él lo muestra `uv run grabar.py --listar`.

## Flujo

### 0. Mira qué hay

```bash
uv run grabar.py --listar
```

Muestra la URL de la app, la carpeta de su código (`APP_DIR`) y las escenas
existentes. Si falla por dependencias, ffmpeg o Chromium, corre
`uv run instalar.py` y sigue sus indicaciones. Si ya existe una escena para la
funcionalidad pedida, modifícala en lugar de crear otra.

### 1. Entiende la funcionalidad en la app real

Busca **selectores estables**, en este orden de preferencia:
1. `data-testid` / `id` (`[data-testid=save]`, `#titulo`)
2. rol + nombre accesible (`role=button[name='Guardar']`)
3. texto visible (`text=Nueva tarea`)
Evita clases generadas (`.css-1x2y3`) y posiciones frágiles.

- **Con `APP_DIR`**: busca en ese código los componentes de la funcionalidad.
- **Sin `APP_DIR`** (o para confirmar): inspecciona la pantalla en vivo.
  ```bash
  uv run grabar.py --inspeccionar /ruta/de/la/pantalla
  ```
  Lista los elementos visibles con su selector sugerido, en celular y
  escritorio, y guarda capturas en `salida/_inspeccion/`: míralas con Read.
  Si no sabes la ruta, pregúntale al usuario o inspecciona `/` y navega.

Mira si la UI cambia entre celular y escritorio (barra inferior, menú
hamburguesa, botón flotante): usa `if d.mobile:` para esos pasos.

### 2. Escribe la escena

Copia `escenas/_plantilla.py` a `escenas/<nombre_en_snake_case>.py`. Una escena
= una funcionalidad = un video de **15–40 s**. Referencia completa de la API y
del guion: `docs/escribir-escenas.md`.

Narración:
- Español rioplatense si la voz es `es-AR-*` (tocá, escribí, tenés); neutro si no.
- Frases cortas y habladas (8–15 palabras), una idea por frase, beneficio antes que mecánica.
- Sin cifras en dígitos ni símbolos ("treinta por ciento", no "30%").
- Puntuación cuidada: los cortes de subtítulo salen de comas y puntos.
- Estructura: qué resuelve (1 frase) → pasos (2–4 frases) → resultado.

Acciones: usa SIEMPRE los métodos de `d.` (`click`, `type`, `select`,
`scroll`, `highlight`, `banner`…), nunca `d.page.click()` directo: en celular
la captura comparte un candado con las acciones de `d.` y un toque directo
puede caer fuera de lugar. Envuelve con `async with d.narrate(...)` las
acciones que ilustran cada frase.

La cuenta demo es compartida por el equipo: en `async def prepare(d)`, que
corre fuera de cámara, deja los datos como deben estar (borra lo creado en una
toma anterior, cierra avisos). Ahí sí se puede usar `d.page` directo.

### 3. Graba

```bash
uv run grabar.py <escena>
```

Si falla un selector: `--perfil mobile --ver` para verlo en vivo, o
`--inspeccionar` sobre esa pantalla; corrige y repite.
Si no hay internet para la voz, `--voz-prueba` para validar el recorrido.

### 4. Verifica antes de reportar

No des la tarea por terminada sin mirar los cuadros. Desde `salida/<escena>`
(si no hay `*-subs.mp4` porque el ffmpeg no tiene libass, usa el `.mp4`
normal y avisa al usuario de lo que indica el grabador para quemarlos):

```bash
ffmpeg -v error -y -i <escena>-mobile-subs.mp4 -vf "fps=1/2.5,scale=240:-1,tile=8x2" -frames:v 1 .work/hoja-mobile.png
ffmpeg -v error -y -i <escena>-desktop-subs.mp4 -vf "fps=1/2.5,scale=480:-1,tile=4x4" -frames:v 1 .work/hoja-desktop.png
```

Lee ambas imágenes con Read y comprueba: la acción ocurre mientras se la
narra, no hay pantallas de error ni de carga, los datos se ven prolijos, no
aparecen emails ni datos personales, y los subtítulos no tapan nada importante.
Revisa también `<escena>-mobile.srt` para confirmar que el texto se lee bien.

Informa las rutas de los `*-subs.mp4` y `landing.html`, la duración y el peso.
Recuérdale al usuario que la escena (`escenas/*.py`) va a git en un PR y los
videos no: se suben a la carpeta compartida del equipo (ver `CONTRIBUTING.md`).

## Ajustes rápidos

| Pedido | Cómo |
|---|---|
| Otra música | `--musica musica/x.mp3` + `--remezclar` (no regraba) |
| Sin música | `--sin-musica --remezclar` |
| Otra voz | `--voz es-AR-TomasNeural` (regraba) |
| Más lento | `PACE = 1.2` en config.py (afecta a todo el equipo: mejor avisar) |
| Subtítulos más grandes | `font_ratio` en `SUBTITLES` + `--remezclar` |
| Solo un formato | `--perfil mobile` o `--perfil desktop` |
