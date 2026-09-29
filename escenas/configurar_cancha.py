"""Configurar una cancha: agregarla al complejo, nombrarla, elegir la modalidad
y darle un horario propio."""

import os

TITLE = "Configurar una cancha"
START = "/league/cmuejep0z00dexas12ubbtl0i/config/venues"
LOGIN = True
PROFILES = ["mobile", "desktop"]

NUEVA = "Cancha Techada"
ROWS = "[data-testid=pitch-row]"
# Lo que deja una toma: la cancha renombrada o, si se cortó antes, el nombre por
# defecto con el que nace (el complejo tiene cuatro). Nada más se borra.
DE_TOMAS_ANTERIORES = {NUEVA, "Cancha 5"}


async def prepare(d):
    """Fuera de cámara: borra la cancha de la toma anterior y oculta el email."""
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
    email = os.environ.get("DEMO_EMAIL")
    if email:
        await page.evaluate("""email => {
            for (const el of document.querySelectorAll('div, span'))
              if (!el.childElementCount && el.textContent.trim() === email)
                el.style.visibility = 'hidden'
        }""", email)


async def run(d):
    await d.banner("Canchas y horarios", 2.2)
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
