"""
Plantilla de escena. Copiala con otro nombre (sin "_" adelante) para crear una:

    cp escenas/_plantilla.py escenas/crear_tarea.py

Cada archivo de escenas/ es una funcionalidad y genera su propio video,
en celular y en escritorio. El nombre del archivo es el nombre del video.
"""

TITLE = "Nombre de la funcionalidad"   # aparece en --listar y en landing.html
START = "/"                            # ruta donde arranca (se abre fuera de cámara)
LOGIN = True                           # hace login antes de grabar (config.login)
PROFILES = ["mobile", "desktop"]       # o solo uno de los dos


async def prepare(d):
    """Opcional, fuera de cámara: dejar la app en el estado justo antes de grabar
    (cerrar un aviso, borrar datos de una prueba anterior, etc.)."""
    pass


async def run(d):
    # Un cartel arriba, como título de la sección (no bloquea).
    await d.banner("Organizá tu día", 2)

    # Narración sola: espera a que termine la frase.
    await d.say("Con Mi App tenés todo tu día a la vista.")

    # Narración mientras pasan cosas: la voz y las acciones van a la vez; al
    # salir del bloque espera a que termine la frase si las acciones fueron más rápidas.
    async with d.narrate("Tocá el botón para crear una tarea nueva."):
        if d.mobile:
            await d.click("role=button[name='Nueva tarea']")   # en celular es un toque
        else:
            await d.click("text=Nueva tarea")                  # en escritorio, cursor animado

    async with d.narrate("Escribí qué tenés que hacer y guardala."):
        await d.type("#titulo", "Llamar a mamá")
        await d.click("text=Guardar")
        await d.highlight("li >> nth=0", 1.5)

    # Tu propia voz grabada en vez de la voz sintética (el texto va a los subtítulos):
    # await d.say("Así de fácil.", audio="voz/asi-de-facil.m4a")
