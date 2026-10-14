---
name: grabar-demo
description: Graba un video demo de una funcionalidad de la PWA del usuario (celular y escritorio) con voz en español, subtítulos y música, para la landing page. Úsala cuando el usuario escriba "/grabar-demo [FUNCIONALIDAD]", pida "grabá/hacé un video de cómo se usa X en mi app", o quiera contenido de demostración para la landing.
argument-hint: "[funcionalidad a mostrar]"
---

# grabar-demo

Convierte "mostrá cómo se hace X en la app" en videos terminados. Tú escribes
la escena (acciones + narración); `grabar.py` navega, graba, pone voz,
subtítulos y música. Este flujo es el mismo en Claude Code, Codex y Copilot.

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
  Antes confirma que está al día con la rama que corre en `APP_URL`
  (`git -C <APP_DIR> fetch` y `git -C <APP_DIR> rev-list --count HEAD..origin/<rama>`):
  un checkout viejo esconde funciones nuevas. Si está atrás, lee esa rama con
  `git show origin/<rama>:<archivo>`, sin hacer checkout.
- **Sin `APP_DIR`** (o para confirmar): inspecciona la pantalla en vivo.
  ```bash
  uv run grabar.py --inspeccionar /ruta/de/la/pantalla
  ```
  Lista los elementos visibles con su selector sugerido, en celular y
  escritorio, y guarda capturas en `salida/_inspeccion/`: ábrelas para ver la pantalla.
  Si no sabes la ruta, pregúntale al usuario o inspecciona `/` y navega.

Mira si la UI cambia entre celular y escritorio (barra inferior, menú
hamburguesa, botón flotante): usa `if d.mobile:` para esos pasos.

Anota todas las formas de hacer la tarea (a mano, importando un Excel, desde
otro menú). Muéstralas o dile al usuario cuál queda afuera: es lo primero
que se nota que falta. Para subir un archivo, `d.upload()` (ver "Subir
archivos" en `docs/escribir-escenas.md`).

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

Zoom: el grabador se acerca solo en zonas con muchos controles juntos o con
objetivos muy chicos, y con movimientos lentos. No lo agregues de más (marea):
usa `zoom=True` solo si un paso importante queda chico y no hubo zoom, y
`zoom=False` si se acercó donde no hacía falta. La intro y el cierre con la
marca van siempre; no hace falta un `banner` que repita el título.

Datos:
- **Nunca escribas un ID en la escena** (de liga, equipo, partido): cada
  entorno tiene los suyos. Usa los datos del login entre llaves:
  `START = "/league/{liga}/config/venues"`; `d.goto()` también los completa.
- En el docstring anota qué necesita la escena en la liga demo ("Necesita: un
  complejo con horario") y súmalo a la tabla "Datos demo" de `CONTRIBUTING.md`.
- La cuenta demo es compartida por el equipo: en `async def prepare(d)`, que
  corre fuera de cámara, deja los datos como deben estar (borra lo creado en
  una toma anterior, cierra avisos). Borra solo lo que crea la escena,
  buscándolo por un nombre propio. Ahí sí se puede usar `d.page` directo.
  Lo que no se pueda limpiar antes de la próxima toma (una liga nueva), se
  deshace en `async def cleanup(d)`, que corre al terminar, aunque falle.

### 3. Graba

```bash
uv run grabar.py <escena>
```

Si falla un selector: `--perfil mobile --ver` para verlo en vivo, o
`--inspeccionar` sobre esa pantalla; corrige y repite.
Si no hay internet para la voz, `--voz-prueba` para validar el recorrido.

### 4. Verifica antes de reportar

No des la tarea por terminada sin mirar los cuadros:

```bash
uv run grabar.py <escena> --hoja
```

Genera una hoja por formato (hasta 16 cuadros repartidos en todo el video) y
muestra dónde quedaron, junto con los `.srt`. Abre las imágenes y comprueba:
la acción ocurre mientras se la narra, no hay pantallas de error ni de carga,
los datos se ven prolijos, no aparecen emails ni datos personales, y los
subtítulos no tapan nada importante. Lee también el `.srt` de celular para
confirmar que el texto se lee bien.

Emails, teléfonos, documentos y los datos de la cuenta se blurean solos (solo
el dato, no el texto que lo rodea). Si ves otro dato personal legible
(nombres de jugadores, direcciones de personas), agrega su selector a
`OFUSCAR["selectores"]` en config.py (o a `textos`) y regraba: el blur se
aplica en la página, no en la mezcla.

Si tu herramienta no puede ver imágenes, pásale las rutas de las hojas a la
persona y pídele que las abra y te confirme antes de seguir.

Si no salieron los `*-subs.mp4` (el ffmpeg no tiene libass), la hoja usa el
video sin subtítulos: avisa al usuario de lo que indica el grabador para
quemarlos.

Informa las rutas de los `*-subs.mp4` y `landing.html`, la duración y el peso.
Recuérdale al usuario que lo que grabó es un **borrador**: la escena
(`escenas/*.py`) va a git en un PR y, después del merge, el video final sale
del workflow "Escenas contra staging" en modo `final` (ver `CONTRIBUTING.md`).

## Ajustes rápidos

| Pedido | Cómo |
|---|---|
| Otra música | `--musica musica/x.mp3` + `--remezclar` (no regraba) |
| Sin música | `--sin-musica --remezclar` |
| Otra voz | `--voz es-AR-TomasNeural` (regraba) |
| Más lento | `PACE = 1.2` en config.py (afecta a todo el equipo: mejor avisar) |
| Subtítulos más grandes | `font_ratio` en `SUBTITLES` + `--remezclar` |
| Solo un formato | `--perfil mobile` o `--perfil desktop` |
| Más o menos zoom, sin intro, otro texto de cierre | `ANIMACIONES` / `MARCA` en config.py + `--remezclar` (afecta a todo el equipo) |
