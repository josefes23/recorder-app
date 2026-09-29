"""
Configuración COMPARTIDA del equipo (va a git): voz, música, subtítulos,
perfiles y el login de la app. Si cambiás algo acá, cambia para todos.

Lo personal va en .env (no va a git): credenciales de la cuenta demo, la URL
de la app (APP_URL) y dónde está su código en tu máquina (APP_DIR).
"""

import os

# --- App --------------------------------------------------------------- #
# La app que se graba. Local por defecto; si no programás, poné en tu .env la
# URL publicada de pruebas:  APP_URL=https://staging.tuapp.com
BASE_URL = os.environ.get("APP_URL") or "http://localhost:5173"

# Carpeta del código de la PWA en tu máquina (opcional). Claude la lee para
# escribir escenas con los selectores correctos; sin ella usa --inspeccionar.
APP_DIR = os.environ.get("APP_DIR") or None

# Si la app no responde, el grabador la levanta con APP_DEV_CMD dentro de
# APP_DIR (y la apaga al terminar). Sin APP_DEV_CMD la levantás vos.
DEV_SERVER = ({"cmd": os.environ["APP_DEV_CMD"], "cwd": APP_DIR}
              if APP_DIR and os.environ.get("APP_DEV_CMD") else None)

SCENES_DIR = "escenas"
OUTPUT_DIR = "salida"


# --- Login (fuera de cámara) ------------------------------------------ #
async def login(page, base_url, env):
    """Se ejecuta antes de empezar a grabar cada escena con LOGIN = True.

    Ajustá los selectores a tu pantalla de login. DEMO_EMAIL / DEMO_PASSWORD
    salen del archivo .env.
    """
    await page.goto(base_url + "/login")
    # La pantalla trae dos formularios (layout celular y escritorio): usar el visible.
    await page.locator("input[name=email]:visible").fill(env["DEMO_EMAIL"])
    await page.locator("input[name=password]:visible").fill(env["DEMO_PASSWORD"])
    await page.locator("button[type=submit]:visible").click()
    await page.wait_for_url(lambda url: "/login" not in url, timeout=20000)


# --- Perfiles de grabación -------------------------------------------- #
# mobile: capturas retina a pantalla completa, como una PWA instalada
#         (390x844 @2x → video 780x1688).
# desktop: screencast a 60 cps (1440x900). Con "scale": 2 sale 2880x1800,
#          más nítido pero con menos cuadros por segundo.
PROFILES = {
    "mobile": {"device": "iPhone 14", "viewport": {"width": 390, "height": 844}, "scale": 2},
    "desktop": {"viewport": {"width": 1440, "height": 900}, "scale": 1},
}
LOCALE = "es-AR"
TIMEZONE = "America/Argentina/Buenos_Aires"
COLOR_SCHEME = "light"          # "dark" si querés mostrar el modo oscuro
SERVICE_WORKERS = "allow"       # "block" si el SW te sirve versiones viejas en dev


# --- Voz --------------------------------------------------------------- #
VOICE = {
    "provider": "edge",           # "edge" (gratis, requiere internet) | "test" (sin red)
    "voice": "es-AR-ElenaNeural", # es-AR-TomasNeural, es-MX-DaliaNeural, es-ES-ElviraNeural…
    "rate": "+0%",
    "pitch": "+0Hz",
}
VOICE_GAP = 0.35   # silencio después de cada frase (s)
PACE = 1.0         # >1 acciones más lentas, <1 más rápidas


# --- Música ------------------------------------------------------------ #
# "auto" = elige una pista de musica/. None = sin música. O una ruta concreta.
MUSIC = {
    "file": "auto",
    "folder": "musica",
    "volume": 0.18,     # volumen base
    "duck": True,       # baja sola mientras habla la voz…
    "duck_level": 0.35, # …a este porcentaje del volumen base
    "voice_volume": 1.0,
}


# --- Subtítulos -------------------------------------------------------- #
SUBTITLES = {
    "burn": True,   # además del .vtt, genera *-subs.mp4 con subtítulos quemados
    "style": {"font": "Arial", "bold": True, "box_alpha": "50", "position": "bottom"},
    # placement "band": franja sólida debajo de la pantalla (nunca tapa la UI:
    #   ideal en celular, donde hay barras inferiores y bottom sheets).
    # placement "overlay": caja semitransparente encima; margin_bottom = distancia
    #   al borde inferior como fracción del alto.
    "mobile": {"max_chars": 30, "max_words": 6, "font_ratio": 0.05,
               "placement": "band", "band_color": "#111111"},
    "desktop": {"max_chars": 48, "max_words": 9, "font_ratio": 0.036,
                "placement": "overlay", "margin_bottom": 0.07},
}


# --- Video ------------------------------------------------------------- #
ACCENT = "#4F7CFF"   # color del toque, el cursor al hacer clic y los resaltados
CRF = 22             # calidad final (menor = mejor y más pesado)
LEAD_IN = 0.6        # segundos quietos al empezar
TAIL = 1.2           # segundos quietos al terminar
POSTER_AT = 1.0      # segundo del que se saca el póster .jpg
KEEP_WORK = True     # conserva la grabación cruda para poder --remezclar
