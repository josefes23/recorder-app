"""
Puente al motor de auto-video-generator.

Ese proyecto se importa como librería y NO se modifica: la app ajusta el estilo
sobrescribiendo sus constantes de módulo en tiempo de ejecución, que es como el
propio generate.py las lee (dentro de las funciones, no en el import).
"""

from __future__ import annotations

import hashlib
import importlib
import io
import re
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT.parent / "auto-video-generator"
DATA = ROOT / "data"
THUMBS = DATA / "thumbs"
PREVIEWS = DATA / "previews"
OUTPUTS = DATA / "outputs"

# El estilo se aplica sobre constantes del generador, que son globales del
# proceso: solo puede haber una previsualización componiendo a la vez.
_preview_lock = threading.Lock()
SCRIPTS = DATA / "scripts"

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# 2,7 palabras/s medido con las voces es-* a --rate +8%.
WORDS_PER_SECOND = 2.7

VOICES = [
    ("es-MX-DaliaNeural", "Dalia — México ♀"),
    ("es-MX-JorgeNeural", "Jorge — México ♂"),
    ("es-ES-ElviraNeural", "Elvira — España ♀"),
    ("es-ES-AlvaroNeural", "Álvaro — España ♂"),
    ("es-ES-XimenaNeural", "Ximena — España ♀"),
    ("es-AR-ElenaNeural", "Elena — Argentina ♀"),
    ("es-AR-TomasNeural", "Tomás — Argentina ♂"),
    ("es-CO-SalomeNeural", "Salomé — Colombia ♀"),
    ("es-CO-GonzaloNeural", "Gonzalo — Colombia ♂"),
    ("es-CL-CatalinaNeural", "Catalina — Chile ♀"),
    ("es-PE-CamilaNeural", "Camila — Perú ♀"),
    ("es-US-PalomaNeural", "Paloma — EE.UU. ♀"),
]

DEFAULT_STYLE = {
    "font_size": 92,
    "stroke": 8,
    "y_ratio": 0.52,
    "max_chars": 30,
    "max_words": 5,
    "max_lines": 3,
    "animate": True,
}


def _import_generator():
    """Importa auto-video-generator/scripts/generate.py como módulo."""
    scripts_dir = GENERATOR / "scripts"
    if not (scripts_dir / "generate.py").is_file():
        raise RuntimeError(
            f"No encuentro el motor en {scripts_dir}. video-studio depende de "
            f"auto-video-generator: deben estar en la misma carpeta padre."
        )
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("generate")


gen = _import_generator()


def apply_style(style: dict) -> None:
    """Vuelca el estilo de la interfaz sobre las constantes del motor."""
    s = {**DEFAULT_STYLE, **(style or {})}
    gen.CAPTION_FONT_SIZE = int(s["font_size"])
    gen.CAPTION_STROKE = int(s["stroke"])
    gen.CAPTION_Y_RATIO = float(s["y_ratio"])
    gen.MAX_CHARS_PER_CAPTION = int(s["max_chars"])
    gen.MAX_WORDS_PER_CAPTION = int(s["max_words"])
    gen.MAX_CAPTION_LINES = int(s["max_lines"])
    # El suelo de autoajuste no puede quedar por encima del tamaño pedido.
    gen.MIN_CAPTION_FONT_SIZE = min(52, int(s["font_size"]))


def clean_script(raw: str) -> str:
    text = re.sub(r"[*_#`\[\]]", " ", raw or "")
    return re.sub(r"\s+", " ", text).strip()


def estimate_seconds(text: str) -> float:
    return len(clean_script(text).split()) / WORDS_PER_SECOND


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60] or "video"


# --------------------------------------------------------------------------- #
# Fondos
# --------------------------------------------------------------------------- #

def background_dir() -> Path:
    return GENERATOR / "assets" / "backgrounds"


def thumbnail(path: Path) -> Path | None:
    """Extrae un fotograma como miniatura; se cachea por nombre+mtime."""
    key = hashlib.md5(f"{path.name}:{path.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    out = THUMBS / f"{key}.jpg"
    if out.exists():
        return out
    THUMBS.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if path.suffix.lower() in VIDEO_EXTS:
        cmd += ["-ss", "2"]
    cmd += ["-i", str(path), "-frames:v", "1", "-vf", "scale=180:320", str(out)]
    try:
        subprocess.run(cmd, check=True, timeout=60)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return out if out.exists() else None


def probe_duration(path: Path) -> float:
    if path.suffix.lower() in IMAGE_EXTS:
        return 0.0
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return round(float(out.stdout.strip()), 1)
    except (ValueError, subprocess.SubprocessError):
        return 0.0


def list_backgrounds() -> list[dict]:
    d = background_dir()
    if not d.is_dir():
        return []
    items = []
    for p in sorted(d.iterdir()):
        if not p.is_file() or p.suffix.lower() not in (VIDEO_EXTS | IMAGE_EXTS):
            continue
        thumb = thumbnail(p)
        items.append({
            "name": p.name,
            "stem": p.stem,
            "group": re.sub(r"_\d+$", "", p.stem),
            "kind": "image" if p.suffix.lower() in IMAGE_EXTS else "video",
            "duration": probe_duration(p),
            "size_mb": round(p.stat().st_size / 1e6, 1),
            "thumb": thumb.name if thumb else None,
        })
    return items


# --------------------------------------------------------------------------- #
# Previsualización: un fotograma en vez de un render de 5 minutos
# --------------------------------------------------------------------------- #

def preview_frame(caption: str, style: dict, background: str | None, topic: str) -> bytes:
    """Compone fondo + subtítulo en un PNG. Tarda ~2 s en lugar de minutos.

    Va entero bajo cerrojo porque `apply_style` escribe en las constantes del
    generador, que son globales del proceso: dos previsualizaciones a la vez se
    pisaban el estilo y devolvían cada una el fotograma de la otra.
    """
    with _preview_lock:
        return _compose_frame(caption, style, background, topic)


def _compose_frame(caption: str, style: dict, background: str | None, topic: str) -> bytes:
    import numpy as np
    from PIL import Image

    apply_style(style)
    PREVIEWS.mkdir(parents=True, exist_ok=True)

    if background:
        bg_path = background_dir() / background
        if not bg_path.is_file():
            bg_path = None
    else:
        bg_path = None

    clip = gen.build_background(bg_path, topic or "preview", 3.0)
    frame = Image.fromarray(np.asarray(clip.get_frame(1.0))).convert("RGBA")
    try:
        clip.close()
    except Exception:
        pass

    text = clean_script(caption).upper() or "TEXTO DE EJEMPLO"
    font = gen.resolve_font(None)
    box_w = int(gen.WIDTH * 0.86)
    size = gen.fit_font_size(text, font, box_w)
    lines = gen.wrap_lines(text, font, size, box_w)
    while len(lines) > gen.MAX_CAPTION_LINES and size > gen.MIN_CAPTION_FONT_SIZE:
        size -= 4
        lines = gen.wrap_lines(text, font, size, box_w)

    overlay = Image.fromarray(gen.render_caption_image(lines, font, size))
    band_center = int(gen.HEIGHT * gen.CAPTION_Y_RATIO) + gen.CAPTION_BOX_H // 2
    frame.alpha_composite(
        overlay,
        ((gen.WIDTH - overlay.width) // 2, band_center - overlay.height // 2),
    )

    buffer = io.BytesIO()
    frame.convert("RGB").resize((405, 720), Image.LANCZOS).save(buffer, format="PNG")
    png = buffer.getvalue()

    # Se deja copia en disco para poder mirarla al depurar, pero lo que viaja al
    # navegador son los bytes: así una previsualización posterior no puede pisar
    # el archivo mientras la respuesta anterior aún se está enviando.
    (PREVIEWS / "preview.png").write_bytes(png)
    return png
