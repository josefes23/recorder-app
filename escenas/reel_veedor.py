"""Reel "Lo que cada uno ve" · el veedor: sus partidos del día, cómo llegar y
la carga del acta desde el celular.

Toma sin narración para el reel. Abre el acta pero no guarda nada.
Necesita: una cuenta de veedor de la liga demo (DEMO_VEEDOR_EMAIL /
DEMO_VEEDOR_PASSWORD en .env), designada en al menos un partido de una fecha
programada (mejor si es de hoy o la próxima), en un complejo con ubicación.
"""

TITLE = "Reel: el veedor"
START = "/league/{liga}/my-home"
LOGIN = True
CUENTA = "veedor"
PROFILES = ["reel"]
ANIMACIONES = {"intro": 0, "cierre": 0, "zoom": 1.0, "subtitulos_palabra": False,
               "transicion": 0.3}


async def run(d):
    await d.wait(1.2)
    await d.goto("/league/{liga}/my-matches")
    await d.wait(0.8)
    await d.click("[data-testid=match-card], [data-testid=match-row]")   # el primer partido
    await d.wait(1.0)
    await d.scroll_to("[data-testid=venue-card]")                        # "cómo llegar"
    await d.wait(1.0)
    await d.click("[data-testid=acta-action], [data-testid=acta-action-early]")
    await d.wait(1.8)
