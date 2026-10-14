"""Reel "Lo que cada uno ve" · el jugador: si juega el sábado y su carnet con QR.

Toma sin narración para el reel.
Necesita: una cuenta de jugador de la liga demo (DEMO_JUGADOR_EMAIL /
DEMO_JUGADOR_PASSWORD en .env), con un próximo partido programado y el carnet
aprobado.
"""

TITLE = "Reel: el jugador"
START = "/league/{liga}/my-season"
LOGIN = True
CUENTA = "jugador"
PROFILES = ["reel"]
ANIMACIONES = {"intro": 0, "cierre": 0, "zoom": 1.0, "subtitulos_palabra": False,
               "transicion": 0.3}


async def run(d):
    await d.wait(1.4)
    await d.scroll(200, duration=1.0)
    await d.wait(0.6)
    await d.goto("/league/{liga}/my-carnet")
    await d.wait(2.2)
