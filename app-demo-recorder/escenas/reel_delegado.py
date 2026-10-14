"""Reel "Lo que cada uno ve" · el delegado: su club y su plantel.

Toma sin narración para el reel.
Necesita: una cuenta de delegado de un club de la liga demo
(DEMO_DELEGADO_EMAIL / DEMO_DELEGADO_PASSWORD en .env), con equipos y jugadores.
"""

TITLE = "Reel: el delegado"
START = "/league/{liga}/my-club"
LOGIN = True
CUENTA = "delegado"
PROFILES = ["reel"]
ANIMACIONES = {"intro": 0, "cierre": 0, "zoom": 1.0, "subtitulos_palabra": False,
               "transicion": 0.3}


async def run(d):
    await d.wait(1.0)
    await d.scroll(260, duration=1.2)
    await d.wait(0.8)
    await d.scroll(260, duration=1.2)
    await d.wait(0.8)
