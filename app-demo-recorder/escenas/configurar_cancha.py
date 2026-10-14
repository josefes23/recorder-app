"""Configurar una cancha: agregarla al complejo, nombrarla, elegir la modalidad
y darle un horario propio.

Necesita en la liga demo: un complejo con horario semanal y ninguna cancha
llamada "Cancha Techada" (ver "Datos demo" en CONTRIBUTING.md).
"""

TITLE = "Configurar una cancha"
START = "/league/{liga}/config/venues"
LOGIN = True
PROFILES = ["mobile", "desktop"]

NUEVA = "Cancha Techada"
ROWS = "[data-testid=pitch-row]"
# Solo se borra la cancha que crea esta escena. Si una toma se corta entre
# "Agregar cancha" y el cambio de nombre, queda una "Cancha N" que no se puede
# distinguir de las reales: borrala a mano.
DE_TOMAS_ANTERIORES = {NUEVA}


async def prepare(d):
    """Fuera de cámara: borra la cancha de la toma anterior."""
    page = d.page  # la captura todavía no empezó: se puede tocar la página directo
    await page.locator("[data-testid=venue-expand]").first.click()
    await page.locator(ROWS).first.wait_for()
    while True:
        names = await page.locator("[data-testid=pitch-name-input]").evaluate_all(
            "els => els.map(e => e.value)")
        sobrantes = [i for i, n in enumerate(names) if n in DE_TOMAS_ANTERIORES]
        if not sobrantes:
            break
        await page.locator(ROWS).nth(sobrantes[0]).locator(
            "[data-testid=pitch-actions-trigger]").click()
        await page.locator("[data-testid=pitch-action-delete]:visible").click()
        await page.locator("[data-testid=confirm-dialog]").get_by_role(
            "button", name="Eliminar", exact=True).click()
        await page.wait_for_function(
            "n => document.querySelectorAll('[data-testid=pitch-row]').length < n",
            arg=len(names))

    await d.goto(START)  # recarga con el complejo cerrado, como lo ve alguien al entrar
    await page.locator("[data-testid=venue-expand]").first.wait_for()


async def run(d):
    await d.say("Cargá tus canchas una sola vez, y el fixture las usa para programar cada fecha.")

    async with d.narrate("Abrí el complejo. Arriba tenés su horario semanal de turnos."):
        await d.click("[data-testid=venue-expand]")
        if d.mobile:
            await d.scroll(420)
        else:
            await d.highlight("[data-testid=venue-week]", 1.6)

    antes = await d.page.locator(ROWS).count()
    nueva = d.page.locator(ROWS).nth(antes)

    async with d.narrate("Tocá agregar cancha, y la nueva ya hereda ese horario."):
        await d.click("[data-testid=pitch-add]")
        await nueva.wait_for()
        await d.highlight(nueva, 1.4)

    async with d.narrate("Ponele un nombre y elegí la modalidad: fútbol cinco, siete u once."):
        await d.type(nueva.locator("[data-testid=pitch-name-input]"), NUEVA)
        await d.press("Enter")
        await d.click(nueva.locator("[data-testid=pitch-modality-f7]"))

    async with d.narrate("¿Esta cancha abre en otro horario? Activá personalizar horario."):
        await d.click(nueva.locator("[data-testid=pitch-custom-toggle]"))
        await d.wait(0.6)
        if d.mobile:
            await d.scroll(360)
        else:
            await d.highlight(nueva, 1.6)

    await d.say("Todo se guarda solo, y esos turnos alimentan el sorteo del fixture.")
