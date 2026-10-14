"""Dar de alta una liga: el asistente de tres pasos, desde el menú de ligas
hasta el centro de configuración de la liga nueva.

Necesita en la liga demo: nada más que la cuenta (arranca en su inicio).
Cada toma crea una liga de verdad. Los nombres de liga son únicos en toda la
plataforma y las ligas no se borran, solo se archivan: prepare() elige el
primer nombre de NOMBRES que la app todavía acepte, y cleanup() archiva la
liga creada para que la cuenta quede como estaba (una liga activa de más
cambiaría a qué liga entra el login de las otras escenas).
"""

import re

TITLE = "Dar de alta una liga"
START = "/league/{liga}/home"
LOGIN = True
PROFILES = ["mobile", "desktop"]

NOMBRES = [
    "Liga Barrio Norte", "Liga del Parque", "Torneo Los Robles", "Liga Villa Sur",
    "Torneo del Oeste", "Liga Costanera", "Torneo Las Lomas", "Liga San Martín",
    "Torneo El Molino", "Liga del Sol", "Torneo Río Chico", "Liga La Loma",
    "Liga Los Álamos", "Torneo Barrio Sur", "Liga Plaza Mayor", "Torneo La Estación",
    "Liga Punta Alta", "Torneo Villa Nueva", "Liga El Ombú", "Torneo Las Acacias",
    "Liga Monte Grande", "Torneo del Litoral", "Liga Santa Rosa", "Torneo Los Pinos",
]


async def prepare(d):
    """Fuera de cámara: elige un nombre libre y anota cómo habla la app con su
    API (para archivar la liga en cleanup)."""
    page = d.page  # la captura todavía no empezó: se puede tocar la página directo
    api = d.datos.setdefault("_api", {})

    def anotar(req):
        if req.headers.get("authorization") and "/leagues" in req.url:
            api["auth"] = req.headers["authorization"]
            api["base"] = req.url.split("/leagues")[0]
    page.on("request", anotar)

    await d.goto("/league/new")
    campo = page.locator("input[name=name]")
    libre = page.locator("[data-testid=wizard-name-available]")
    ocupado = page.locator("[data-testid=wizard-name-taken]")
    for nombre in NOMBRES:
        await campo.fill(nombre)
        await page.wait_for_timeout(600)          # la app pregunta después de una pausa
        await libre.or_(ocupado).wait_for(timeout=10000)
        if await libre.is_visible():
            d.datos["nombre"] = nombre
            break
    else:
        raise SystemExit("ERROR: ya se usaron todos los nombres de NOMBRES: sumá otros.")

    await d.goto(START)


async def run(d):
    await d.say("Crear tu liga en TuLigaPro lleva tres pasos.")

    async with d.narrate("Abrí el menú de ligas y tocá crear una liga."):
        if d.mobile:
            await d.click("[data-testid=shell-switcher-mobile]")
            await d.click("[data-testid=switcher-action-join-or-create]")
        else:
            await d.click("[data-testid=shell-switcher]")
            await d.click("[data-testid=switcher-action-create]")

    async with d.narrate("Ponele nombre y elegí si va a ser pública o privada."):
        await d.type("input[name=name]", d.datos["nombre"])
        await d.page.locator("[data-testid=wizard-name-available]").wait_for(timeout=10000)
        await d.click("[data-testid=visibility-card-public]")
        await d.click("[data-testid=wizard-next]")

    async with d.narrate("Si todavía no tenés la planilla de jugadores, "
                         "empezá por la primera división."):
        await d.click("[data-testid=load-mode-scratch]")
        await d.click("[data-testid=wizard-next]")

    async with d.narrate("Revisá el nombre de la división y tocá crear liga."):
        await d.type("input[name=divisionName]", "Primera")
        await d.click("[data-testid=wizard-create-league]")

    async with d.narrate("Confirmás el resumen, y la liga queda creada."):
        await d.highlight("[data-testid=commit-confirm-items]", 1.4)
        await d.click("[data-testid=commit-confirm-accept]")
        await d.page.wait_for_url(re.compile(r"/league/[^/]+/config$"), timeout=20000)
        d.datos["nueva"] = _liga_en(d.page.url)

    async with d.narrate("Desde acá seguís con las divisiones, las canchas, "
                         "la puntuación y las sanciones."):
        await d.wait(0.8)
        await d.highlight("[data-testid=shell-switcher-mobile]" if d.mobile
                          else "[data-testid=shell-switcher]", 1.6)


async def cleanup(d):
    """Fuera de cámara, al terminar (aunque la toma falle): archiva la liga
    que se creó. Si run() se cortó antes de anotarla, la toma de la URL."""
    nueva = d.datos.get("nueva") or _liga_en(d.page.url)
    if not nueva or nueva == d.datos.get("liga"):
        return  # la toma no llegó a crear la liga
    api = d.datos.get("_api", {})
    nombre = d.datos.get("nombre", nueva)
    if not api.get("auth"):
        print(f"   AVISO: no se pudo archivar «{nombre}»: archivala a mano.")
        return
    error = await archivar_liga(d.page.request, api["base"], api["auth"], nueva)
    print(f"   Liga de la toma «{nombre}» archivada." if not error else
          f"   AVISO: no se pudo archivar «{nombre}» ({error}): archivala a mano.")


async def archivar_liga(request, base: str, auth: str, liga: str) -> str | None:
    """Archiva una liga creada por el asistente. La API no archiva ligas con
    divisiones activas: primero borra la que creó el asistente, que todavía
    no tiene equipos. Devuelve el error, o None si salió bien."""
    h = {"Authorization": auth}
    r = await request.get(f"{base}/leagues/{liga}/divisions", headers=h)
    if not r.ok:
        return f"listar sus divisiones devolvió {r.status}"
    for div in (await r.json()).get("divisions", []):
        r = await request.delete(f"{base}/divisions/{div['id']}", headers=h)
        if not r.ok:
            return f"borrar la división «{div.get('name', div['id'])}» devolvió {r.status}"
    r = await request.delete(f"{base}/leagues/{liga}", headers=h)
    return None if r.ok else f"archivarla devolvió {r.status}"


def _liga_en(url: str) -> str | None:
    m = re.search(r"/league/(?!new\b)([^/?#]+)", url)
    return m.group(1) if m else None
