"""Reel "Lo que cada uno ve" · el hincha: la página pública de la liga, sin
cuenta (resumen, fixture y tabla).

Toma sin narración para el reel. Entra como organizador solo para saber el ID
de la liga y después cierra la sesión, fuera de cámara: lo que se graba es lo
que ve cualquiera con el link.
Necesita: la liga demo con "Liga pública" encendida, fixture y resultados.
"""

TITLE = "Reel: el hincha"
START = "/league/{liga}/public"
LOGIN = True
PROFILES = ["reel"]
ANIMACIONES = {"intro": 0, "cierre": 0, "zoom": 1.0, "subtitulos_palabra": False,
               "transicion": 0.3}


async def prepare(d):
    """Fuera de cámara: sale de la cuenta, como un hincha que abre el link."""
    await d.page.context.clear_cookies()
    await d.page.evaluate("() => { localStorage.clear(); sessionStorage.clear() }")
    await d.goto(START)


async def run(d):
    await d.wait(1.2)
    await d.goto("/league/{liga}/public/schedule")
    await d.wait(0.6)
    await d.scroll(220, duration=1.0)
    await d.goto("/league/{liga}/public/standings")
    await d.wait(1.6)
