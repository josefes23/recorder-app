"""Reel "Lo que cada uno ve" · el organizador: recorre las pantallas con las
que maneja toda la liga (inicio, fixture, tabla, canchas, clubes).

Toma sin narración para el reel: la voz y los subtítulos los pone el reel.
Necesita en la liga demo: fixture con fechas, resultados cargados (para que la
tabla tenga puntos), un complejo con canchas y clubes con equipos.
"""

TITLE = "Reel: el organizador"
START = "/league/{liga}/home"
LOGIN = True
CUENTA = "organizador"
PROFILES = ["reel"]
# Tomas para montar: sin placas ni zoom, con fundido entre pantallas.
ANIMACIONES = {"intro": 0, "cierre": 0, "zoom": 1.0, "subtitulos_palabra": False,
               "transicion": 0.3}

PANTALLAS = ["/league/{liga}/home", "/league/{liga}/schedule", "/league/{liga}/standings",
             "/league/{liga}/config/venues", "/league/{liga}/clubs"]


async def run(d):
    for i, ruta in enumerate(PANTALLAS):
        if i:
            await d.goto(ruta)
        await d.wait(0.6)
        await d.scroll(160, duration=0.8)    # un poco de movimiento en cada pantalla
        await d.wait(0.3)
