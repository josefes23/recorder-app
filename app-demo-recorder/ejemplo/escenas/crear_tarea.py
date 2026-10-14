"""Escena de ejemplo: crear una tarea y marcarla como hecha."""

TITLE = "Crear y completar una tarea"
START = "/#/tareas"
LOGIN = True
PROFILES = ["mobile", "desktop"]


async def run(d):
    await d.banner("Organizá tu día", 2.2)
    await d.say("Con Tareitas tenés todo tu día a la vista, en un solo lugar.")

    async with d.narrate("¿Algo nuevo para hacer? Tocá el botón de nueva tarea."):
        if d.mobile:
            await d.click("button.fab")
        else:
            await d.click("#nueva")

    async with d.narrate("Escribí qué tenés que hacer y elegí una categoría."):
        await d.type("#titulo", "Llamar a mamá")
        await d.select("#cat", "Casa")

    async with d.narrate("Guardala, y aparece arriba de todo."):
        await d.click("text=Guardar tarea")
        await d.highlight("li >> nth=0", 1.4)

    async with d.narrate("Cuando la termines, marcala con un toque. El progreso se actualiza solo."):
        await d.click("li >> nth=0 >> .chk")
        await d.highlight(".stats", 1.6)
