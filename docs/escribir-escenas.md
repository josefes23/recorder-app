# Escribir una escena

Una escena es un archivo `escenas/<nombre>.py` que describe una funcionalidad:
qué se toca y qué se dice. El nombre del archivo es el nombre del video.
Con Claude Code, `/grabar-demo` la escribe por vos; esta guía es para
escribirla o corregirla a mano.

Empezá copiando la plantilla (el `_` adelante hace que no se grabe):

```bash
cp escenas/_plantilla.py escenas/crear_tarea.py
```

En Windows (PowerShell): `copy escenas\_plantilla.py escenas\crear_tarea.py`.

## Estructura

```python
TITLE = "Crear una tarea"          # aparece en --listar y en landing.html
START = "/tareas"                  # ruta donde arranca (se abre fuera de cámara)
LOGIN = True                       # hace login antes de grabar (config.login)
PROFILES = ["mobile", "desktop"]   # o solo uno


async def prepare(d):
    """Fuera de cámara: dejar la app lista (borrar lo de una toma anterior…)."""


async def run(d):
    await d.say("Con Mi App tenés todo tu día a la vista.")
    async with d.narrate("Tocá el botón para crear una tarea."):
        await d.click("text=Nueva tarea")
    async with d.narrate("Escribí qué tenés que hacer y guardala."):
        await d.type("#titulo", "Llamar a mamá")
        await d.click("text=Guardar")
```

## Acciones

| Acción | Qué hace |
|---|---|
| `await d.say(texto)` | Narra y espera a que termine la frase |
| `async with d.narrate(texto):` | Narra mientras ocurren las acciones del bloque |
| `await d.say(texto, audio="voz/x.m4a")` | Usa una voz grabada; el texto va a los subtítulos |
| `await d.click(obj)` | Cursor animado en escritorio, toque en celular |
| `await d.type(obj, texto)` | Tipeo visible, letra por letra |
| `await d.select(obj, valor)` / `d.press("Enter")` / `d.hover(obj)` | |
| `await d.scroll(600)` / `d.scroll_to(obj)` | Desplazamiento suave |
| `await d.highlight(obj, 1.5)` | Remarca un elemento y oscurece el resto |
| `await d.banner("Texto", 2)` | Cartel arriba, como título de sección |
| `await d.wait(1)` / `d.goto("/ruta")` | |
| `d.mobile`, `d.profile`, `d.page` | Para variar según el perfil o usar Playwright directo |

`obj` es un selector de Playwright (`"text=Guardar"`, `"#email"`,
`"role=button[name='Guardar']"`) o un Locator (`d.page.get_by_role(...)`).

**Dentro de `run()` usá siempre las acciones de `d.`**, no `d.page.click()`:
mientras se graba en celular, un toque directo puede caer fuera de lugar (ver
[cómo funciona](como-funciona.md#toques-durante-la-captura)). En `prepare()`
todavía no se graba, así que ahí sí se puede usar `d.page`.

## Encontrar los selectores

Preferí, en este orden:

1. `data-testid` o `id`: `[data-testid=pitch-add]`, `#titulo`
2. rol + nombre: `role=button[name='Guardar']`
3. texto visible: `text=Nueva tarea`

Evitá las clases generadas (`.css-1x2y3`) y las posiciones (`nth=3`) cuando
haya otra opción.

Si no tenés el código de la app, inspeccioná la pantalla:

```bash
uv run grabar.py --inspeccionar /ruta/de/la/pantalla
```

Lista cada botón, campo y enlace visible con el selector sugerido, en celular
y escritorio, y guarda capturas en `salida/_inspeccion/`.

## Celular y escritorio

La misma escena se graba en los dos formatos. Si la interfaz cambia (barra
inferior, menú hamburguesa, botón flotante), separá esos pasos:

```python
if d.mobile:
    await d.click("role=button[name='Nueva tarea']")
else:
    await d.click("text=Nueva tarea")
```

## Consejos de guion

- Frases cortas y habladas, 8–15 palabras. Una idea por frase.
- Cifras en letras ("treinta por ciento"): el TTS las lee mejor.
- Puntuación cuidada: los subtítulos se cortan en comas y puntos.
- Cada escena, 15–40 segundos. Varias escenas cortas rinden más que un tour largo.
- Datos demo prolijos: nombres reales, nada de "test123".
