---
name: corregir-demo
description: 'Corrige un video demo ya grabado con grabar.py a partir de lo que la persona le vio mal o echó en falta, sin rehacerlo desde cero: un paso o una alternativa que no se mostró (ej. "en el alta faltó cargar desde un Excel"), narración equivocada, acciones que no coinciden con la voz, algo que no se ve, datos feos, ritmo, música o subtítulos. Úsala cuando escriban "/corregir-demo [qué corregir]" o comenten un video ya hecho ("al video le faltó…", "no dice que…", "va muy rápido", "no se ve…", "corregí el demo de…"), o traigan los comentarios de la revisión del PR de una escena. Si la funcionalidad todavía no tiene escena, usa /grabar-demo.'
argument-hint: "[video y qué corregir]"
---

# corregir-demo

Toma una escena ya grabada y lo que la persona le vio mal, y la deja corregida.
Es una edición, no una reescritura: lo que estaba bien se conserva (sus frases
ya están en la caché de voz y mantienen el ritmo que la persona aprobó).

Mismas reglas que `/grabar-demo` (`.claude/skills/grabar-demo/SKILL.md`):
trabajas en la raíz del repo, ejecutas SIEMPRE con `uv run`, **no lees `.env`**
y dentro de `run()` usas solo los métodos de `d.`. La API está en
`recorder/demo.py` y la guía de escenas en `docs/escribir-escenas.md`.

## Flujo

### 0. Ubica la escena y mira qué muestra hoy

```bash
uv run grabar.py --listar
```

La gente nombra los videos por lo que muestran ("el del alta", "el de las
canchas"), no por el archivo: búscalo por `TITLE`, nombre y docstring. Si dos
escenas encajan o ninguna, pregunta. Si no hay escena para eso, no es una
corrección: sigue `/grabar-demo`.

Antes de tocar nada, lee:
- `escenas/<escena>.py`: qué se hace y qué se dice.
- `salida/<escena>/<escena>-mobile.srt`: en qué segundo cae cada frase. Si no
  está, `salida/<escena>/.work/<perfil>/timeline.json` tiene lo mismo (inicio y
  duración de cada narración).
- Si el video está grabado, sus cuadros: `uv run grabar.py <escena> --hoja`.
  Ubica en el tiempo cada cosa que te marcaron.

Mira también si alguien más está tocando esa escena: `git status` y la fecha
del archivo. Si cambió hace minutos, avisa a la persona y, cuando edites,
vuelve a leerla justo antes, para trabajar sobre la última versión. No
grabes la misma escena a la vez que otro: la cuenta demo es compartida y un
`prepare()` borraría lo del otro.

### 1. Arma la lista de correcciones

El comentario suele ser corto ("faltó el Excel"). Tradúcelo a ítems
verificables: **qué está mal → qué se tiene que ver o escuchar → dónde**
(perfil y segundo). Esa lista guía todo lo que sigue y es lo que vas a
comprobar al final.

Si en los cuadros ves otros problemas (la lista de revisión de
`CONTRIBUTING.md`), anótalos aparte como propuestas: la persona pidió algo
concreto y tiene que saber qué más cambió.

### 2. Encuentra la causa

| Lo que te dicen | Causa habitual | Qué tocar | ¿Regraba? |
|---|---|---|---|
| "Faltó mostrar X" / "también se puede hacer X" | La escena se escribió mirando otra versión de la app, o mostró un solo camino | Investigar X (paso 2b) y sumar pasos y narración | Sí |
| "Dice algo que no es así" | Guion | Texto de `say`/`narrate` | Sí |
| "Lo hace antes o después de decirlo" | La acción está en otro bloque `narrate`, o la frase dura más que la acción | Mover la acción a su bloque; partir la frase | Sí |
| "No se llega a ver" / "va muy rápido" | Poco tiempo sobre el resultado | `d.highlight(obj, s)` o una frase que lo acompañe. `PACE` en config.py cambia los videos de todos: no | Sí |
| "Queda largo" | Frases o pasos que sobran | Cortar frases, sacar pasos obvios | Sí |
| "No se ve X" | Fuera de pantalla, o la UI de celular es otra | `d.scroll_to(obj)`, `if d.mobile:` | Sí |
| "Aparece un error, un cargando, un aviso" | Espera fija o datos en mal estado | `await locator.wait_for()` en vez de `d.wait`; ordenar en `prepare()` | Sí |
| "Datos feos", "se ve un email" | Datos demo | `prepare()`, nombres creíbles, ocultar el email como en `configurar_cancha.py` | Sí |
| Música, volumen, tamaño de subtítulos | Mezcla | `--musica`, `--sin-musica`, `SUBTITLES` en config.py + `--remezclar` | No |
| Otra voz | | `--voz …` | Sí |

Cambiar el texto de una frase cambia su duración: por eso casi todo regraba.
Solo la mezcla (música, volúmenes, estilo de subtítulos) sale con
`--remezclar` en segundos.

#### 2b. Si falta algo, búscalo en la app que se graba

Suele faltar por una de dos razones: la escena recorre un solo camino y la
pantalla ofrece otro (ej. eligió "cargar a mano" y nunca tocó "subir mis
jugadores"), o se escribió leyendo código más viejo que el que corre en
`APP_URL`. Para encontrarla:

- **Lista todas las formas de hacer la tarea** (a mano, importando un
  archivo, desde otro menú) y cuál muestra el video. Empieza por las opciones
  que ya aparecen en pantalla y la escena no toca.
- **Con `APP_DIR`**, lee la rama que está en staging, no el checkout local,
  que puede estar muy atrás. Si no sabes cuál es, pregunta. Sin cambiar de
  rama: `git -C <APP_DIR> fetch`, después
  `git -C <APP_DIR> rev-list --count HEAD..origin/<rama>` (cuánto está atrás),
  `git -C <APP_DIR> grep -n "<patrón>" origin/<rama> -- <carpeta>` y
  `git -C <APP_DIR> show origin/<rama>:<archivo>`. No hagas checkout ni pull
  en ese repo sin preguntar: puede haber trabajo sin guardar.
- **En la pantalla real**, que es lo que se graba (si `APP_URL` es local,
  puede estar corriendo otro checkout que `APP_DIR`):
  `uv run grabar.py --inspeccionar /ruta` y abre las capturas de
  `salida/_inspeccion/`. Solo llega a pantallas con ruta propia. Los pasos
  de un asistente o un diálogo léelos en el código, o míralos con `--ver` en
  una toma de prueba, si la escena no crea datos que no se puedan limpiar.
- Si la función no está en esa `APP_URL`, díselo a la persona: no la simules.

### 3. Decide si entra en la misma escena

Una escena = una funcionalidad = un video de 15 a 40 s. Estima la duración
nueva con el ritmo real de esta voz, no a ojo: saca las palabras por segundo
del `.srt` actual (suele dar unos 5 s por frase de 10–12 palabras), súmale
lo que tardan las acciones y las esperas de la app.

- Si entra, va en la misma escena, recortando otras frases si hace falta.
- Si se pasa de 40 s, **pregúntale a la persona** antes de seguir. Hay tres
  opciones:
  - **Mostrar el otro camino en lugar del actual.** Conviene cuando el camino
    que faltaba es el más completo, o el que se quiere vender.
  - **Una mención corta aquí y una escena aparte** con `/grabar-demo` (ej.
    `importar_jugadores_excel`). Conviene si ese camino se puede grabar solo.
    Si solo existe dentro del mismo flujo, la escena aparte repite todo el
    recorrido.
  - **Alargar este video.**

  Recomienda una y di por qué.

### 4. Corrige la escena

- Cambia solo lo que pide la corrección. Si decidiste cambiar de camino, eso
  es la corrección, pero conserva igual el arranque, el cierre y las frases
  que siguen valiendo.
- Las frases nuevas siguen el guion de `/grabar-demo` (rioplatense con voz
  `es-AR-*`, 8–15 palabras, cifras en letras, beneficio antes que mecánica) y
  el hilo de la escena: qué resuelve → pasos → resultado.
- Si la acción cambia entre celular y escritorio, usa `if d.mobile:`.
- **Subir un archivo** (Excel, CSV, imagen):
  `await d.upload(obj, "escenas/archivos/<archivo>")` toca el botón o la zona
  de subir, como un `d.click`, y carga el archivo sin abrir el diálogo del
  sistema, que no se puede grabar. El archivo:
  - va en `escenas/archivos/` y a git, porque los finales del workflow
    también lo necesitan;
  - parte de la plantilla de la app si la tiene (un "descargar plantilla"; en
    `APP_DIR` suele estar en `public/`);
  - cumple lo que valida el importador (columnas obligatorias, formatos,
    cantidad mínima de filas). Léelo en su código: un archivo que dispara
    avisos arruina la toma;
  - lleva datos inventados y creíbles, nunca de personas reales, y las filas
    justas para pasar la validación y que la vista previa se lea bien;
  - se crea o edita con `uv run --with openpyxl python <script>`, con el
    script en tu carpeta temporal y no en el repo.
- **Lo que la corrección crea en cámara** (jugadores importados, un equipo,
  una liga) queda en la cuenta demo, que es compartida: `prepare()` lo deja
  como estaba antes de cada toma. Encuéntralo por algo propio de la escena,
  como los nombres del archivo o la liga que crea la toma. La app puede
  negarse a borrarlo (ej. no deja archivar una liga con divisiones, ni borrar
  una división con equipos): borra en orden, de lo de adentro a lo de afuera,
  y haz que `prepare()` falle con un error claro si no pudo limpiar, en vez
  de seguir en silencio. Lo que no se pueda limpiar desde la app, díselo a la
  persona y anótalo en "Datos demo" de `CONTRIBUTING.md`.
- Si la escena necesita datos nuevos en la liga demo, actualiza el
  "Necesita" del docstring y la tabla "Datos demo" de `CONTRIBUTING.md`.

### 5. Regraba y comprueba cada ítem

```bash
uv run grabar.py <escena> --perfil mobile   # mientras ajustas; --ver para mirarlo en vivo
uv run grabar.py <escena>                   # al final, los dos formatos
uv run grabar.py <escena> --hoja
```

Si falla un selector, `--inspeccionar` sobre esa pantalla, corrige y repite.

Revisa **cada ítem de la lista del paso 1** en los cuadros y en el `.srt`:
que se vea lo que tiene que verse mientras se lo narra (ej. el Excel
subiéndose y la vista previa con las filas). La hoja reparte 16 cuadros en
todo el video y un momento corto puede quedar entre dos: para mirar un
segundo puntual, `ffmpeg -ss <segundo> -i salida/<escena>/<escena>-mobile-subs.mp4 -frames:v 1 salida/<escena>/.work/cuadro-<segundo>.png`.
Pasa además la revisión general del paso 4 de `/grabar-demo` (sin errores ni
emails, subtítulos que no tapan nada, 15–40 s).

Si no puedes ver imágenes, pásale las rutas a la persona y pídele que te
confirme cada ítem.

### 6. Informa

- Cada corrección: qué cambió y cómo lo comprobaste (cuadro o segundo).
- Las propuestas que no aplicaste.
- Duración antes → después y las rutas de los `*-subs.mp4` y `landing.html`.
- Los archivos tocados (la escena, `escenas/archivos/…`, `CONTRIBUTING.md`).
- Que es un **borrador**: la escena (y su archivo en `escenas/archivos/`) va
  a git en un PR y el video final sale del workflow "Escenas contra staging"
  (ver `CONTRIBUTING.md`).
