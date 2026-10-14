#!/usr/bin/env python3
"""
Generador automatizado de Reels/Shorts (9:16, 1080x1920).

Flujo:
  1. Guion   -> recibido por --script/--script-file (lo escribe Claude) o plantilla local.
  2. Voz     -> edge-tts, voz neuronal en español, sin API key.
  3. Video   -> moviepy: fondo + audio + subtítulos sincronizados palabra a palabra.

Uso:
  python scripts/generate.py --topic "El café y la productividad"
  python scripts/generate.py --topic "..." --script-file tmp/guion.txt --voice es-ES-ElviraNeural
"""

from __future__ import annotations

import argparse
import asyncio
import colorsys
import hashlib
import math
import os
import random
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# Configuración global
# --------------------------------------------------------------------------- #

ROOT = Path(__file__).resolve().parent.parent
BACKGROUNDS_DIR = ROOT / "assets" / "backgrounds"
FONTS_DIR = ROOT / "assets" / "fonts"
OUTPUTS_DIR = ROOT / "outputs"
TMP_DIR = ROOT / "tmp"

WIDTH, HEIGHT = 1080, 1920
FPS = 30

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

DEFAULT_VOICE = "es-MX-DaliaNeural"

# Fuentes candidatas en macOS, de más a menos preferida.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]

# Subtítulos
MAX_CHARS_PER_CAPTION = 30
MAX_WORDS_PER_CAPTION = 5
CAPTION_FONT_SIZE = 92
MIN_CAPTION_FONT_SIZE = 52   # suelo al autoajustar palabras largas
CAPTION_STROKE = 8
MAX_CAPTION_LINES = 3       # tope de líneas por bloque
CAPTION_BOX_H = 400          # banda fija: el bloque no se desplaza según nº de líneas
CAPTION_Y_RATIO = 0.52       # borde superior de la banda (deja libre la UI de Reels)
PUNCT = ".,;:?!…"


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def step(n: int, total: int, msg: str) -> None:
    print(f"\n[{n}/{total}] {msg}", flush=True)


# --------------------------------------------------------------------------- #
# 1. Guion
# --------------------------------------------------------------------------- #

def build_fallback_script(topic: str) -> str:
    """
    Plantilla de respaldo cuando no se recibe un guion escrito por Claude.
    Estructura: gancho -> contexto -> 3 ideas -> cierre con llamada a la acción.
    """
    t = topic.strip().rstrip(".")
    return (
        f"¿Y si te dijera que casi todo lo que crees sobre {t} está incompleto? "
        f"Quédate treinta segundos, porque esto te va a cambiar la perspectiva. "
        f"Primero: {t} no es cuestión de suerte, es cuestión de sistema. "
        f"Segundo: la mayoría abandona justo antes del punto donde empieza a funcionar. "
        f"Y tercero, lo más importante: pequeñas decisiones repetidas superan a cualquier "
        f"golpe de talento aislado. "
        f"Aplica solo una de estas tres ideas esta semana y nota la diferencia. "
        f"Sígueme para más."
    )


def load_script(args: argparse.Namespace) -> str:
    if args.script_file:
        path = Path(args.script_file).expanduser()
        if not path.is_file():
            sys.exit(f"ERROR: no existe el archivo de guion: {path}")
        raw = path.read_text(encoding="utf-8")
        log(f"Guion cargado desde {path.name}")
    elif args.script:
        raw = args.script
        log("Guion recibido por parámetro --script")
    else:
        raw = build_fallback_script(args.topic)
        log("Sin guion externo: usando plantilla local de respaldo")

    # Normaliza: quita marcas de formato y espacios sobrantes.
    clean = re.sub(r"[*_#`\[\]]", " ", raw)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        sys.exit("ERROR: el guion quedó vacío tras la limpieza.")
    return clean


# --------------------------------------------------------------------------- #
# 2. Voz (edge-tts) + marcas de tiempo por palabra
# --------------------------------------------------------------------------- #

async def _synthesize(text: str, voice: str, rate: str, pitch: str, out_mp3: Path):
    """Genera el mp3 y devuelve los eventos WordBoundary con tiempos reales."""
    import edge_tts

    # edge-tts 7.x emite SentenceBoundary por defecto; necesitamos precisión por palabra.
    communicate = edge_tts.Communicate(
        text, voice, rate=rate, pitch=pitch, boundary="WordBoundary"
    )
    words: list[dict] = []

    with open(out_mp3, "wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offset/duration vienen en unidades de 100 nanosegundos.
                words.append(
                    {
                        "text": chunk["text"],
                        "start": chunk["offset"] / 1e7,
                        "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                    }
                )
    return words


def synthesize_voice(text: str, voice: str, rate: str, pitch: str, out_mp3: Path) -> list[dict]:
    words = asyncio.run(_synthesize(text, voice, rate, pitch, out_mp3))
    size_kb = out_mp3.stat().st_size / 1024
    if size_kb < 1:
        sys.exit("ERROR: edge-tts devolvió un audio vacío. Revisa tu conexión a internet.")
    log(f"Audio generado: {out_mp3.name} ({size_kb:.0f} KB, {len(words)} palabras marcadas)")
    return words


# --------------------------------------------------------------------------- #
# 3. Subtítulos: agrupar palabras en bloques legibles
# --------------------------------------------------------------------------- #

def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s, flags=re.UNICODE).lower()


def attach_punctuation(words: list[dict], script_text: str) -> list[dict]:
    """
    edge-tts devuelve las palabras sin puntuación, así que los cortes por frase
    nunca se detectarían. Reasignamos el signo final de cada palabra leyéndolo
    del guion original, avanzando en paralelo con una ventana de tolerancia
    (por si el TTS verbaliza cifras o abreviaturas de forma distinta).
    """
    tokens = re.findall(r"\S+", script_text)
    ti = 0
    for w in words:
        w["punct"] = ""
        target = _norm(w["text"])
        if not target:
            continue
        j, limit = ti, min(len(tokens), ti + 6)
        while j < limit and _norm(tokens[j]) != target:
            j += 1
        if j < limit:
            last = tokens[j][-1]
            w["punct"] = last if last in PUNCT else ""
            ti = j + 1
    return words


def _split_sentences(words: list[dict]) -> list[list[dict]]:
    """Parte la lista de palabras en frases usando la puntuación fuerte."""
    sentences, current = [], []
    for w in words:
        current.append(w)
        # Tupla, no cadena: `"" in ".?!…"` sería True y cortaría en cada palabra.
        if w.get("punct") in (".", "?", "!", "…"):
            sentences.append(current)
            current = []
    if current:
        sentences.append(current)
    return sentences


def _balance(sentence: list[dict]) -> list[list[dict]]:
    """
    Reparte una frase en bloques de tamaño parejo.

    Cortar en cuanto se llega al límite deja colas huérfanas: "sino lo que haces"
    + "antes" sola en pantalla 0,6 s. Calculamos cuántos bloques hacen falta y
    repartimos las palabras a partes iguales, así ningún bloque queda suelto.
    """
    if not sentence:
        return []
    n_chars = math.ceil(len(" ".join(w["text"] for w in sentence)) / MAX_CHARS_PER_CAPTION)
    n_words = math.ceil(len(sentence) / MAX_WORDS_PER_CAPTION)
    n = max(1, n_chars, n_words)

    base, extra = divmod(len(sentence), n)
    blocks, i = [], 0
    for b in range(n):
        size = base + (1 if b < extra else 0)
        if size:
            blocks.append(sentence[i : i + size])
            i += size
    return blocks


def group_captions(words: list[dict]) -> list[dict]:
    """Agrupa palabras en bloques legibles, equilibrados y sin huecos."""
    captions: list[dict] = []
    for sentence in _split_sentences(words):
        for block in _balance(sentence):
            captions.append(
                {
                    "text": " ".join(w["text"] for w in block).strip(),
                    "start": block[0]["start"],
                    "end": block[-1]["end"],
                }
            )

    # Cada bloque dura hasta que arranca el siguiente. Sin esto, las pausas del
    # TTS tras cada punto (~0,8 s) dejan la pantalla sin texto y parpadea.
    for i, cap in enumerate(captions):
        if i + 1 < len(captions):
            cap["end"] = max(cap["end"], captions[i + 1]["start"])
        else:
            cap["end"] += 0.40
        cap["duration"] = max(0.30, cap["end"] - cap["start"])
    return captions


def captions_from_text(text: str, duration: float) -> list[dict]:
    """Respaldo si el servicio no devolvió marcas de tiempo: reparto proporcional."""
    chunks = textwrap.wrap(text, width=MAX_CHARS_PER_CAPTION)
    total_chars = sum(len(c) for c in chunks) or 1
    caps, t = [], 0.0
    for c in chunks:
        d = duration * len(c) / total_chars
        caps.append({"text": c, "start": t, "end": t + d, "duration": d})
        t += d
    return caps


# --------------------------------------------------------------------------- #
# 4. Fondo
# --------------------------------------------------------------------------- #

def resolve_font(explicit: str | None) -> str:
    if explicit:
        if not Path(explicit).is_file():
            sys.exit(f"ERROR: no existe la fuente indicada: {explicit}")
        return explicit
    for f in sorted(FONTS_DIR.glob("*.tt[fc]")) + sorted(FONTS_DIR.glob("*.otf")):
        return str(f)
    for cand in FONT_CANDIDATES:
        if Path(cand).is_file():
            return cand
    sys.exit("ERROR: no se encontró ninguna fuente TTF. Coloca una en assets/fonts/.")


def pick_background(
    explicit: str | None, match: str | None = None, exclude: set[Path] | None = None
) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_file():
            sys.exit(f"ERROR: no existe el fondo indicado: {p}")
        return p
    pool = [
        p for p in BACKGROUNDS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in (VIDEO_EXTS | IMAGE_EXTS)
    ] if BACKGROUNDS_DIR.is_dir() else []

    if match and pool:
        # fetch_backgrounds.py nombra los archivos con el slug de la búsqueda
        # ("woman-sleeping-bed_9787496.mp4"), así que basta con buscar en el nombre.
        terms = [t for t in re.split(r"[^\w]+", match.lower()) if len(t) > 2]
        narrowed = [p for p in pool if any(t in p.stem.lower() for t in terms)]
        if narrowed:
            log(f"{len(narrowed)} fondos coinciden con '{match}'")
            pool = narrowed
        else:
            log(f"AVISO: ningún fondo coincide con '{match}'; se elige al azar. "
                f"Descarga más con: scripts/fetch_backgrounds.py --query \"{match}\"")

    # Evita repetir clip entre segmentos, salvo que no quede alternativa.
    if exclude:
        fresh = [p for p in pool if p not in exclude]
        if fresh:
            pool = fresh

    return random.choice(pool) if pool else None


def parse_bg_plan(spec: str, duration: float) -> list[tuple[str, float, float]]:
    """
    Traduce "sleeping,coffee@7.3,alarm@25.5" a segmentos (término, inicio, fin).

    El `@segundo` marca dónde entra cada fondo; los términos sin marca se reparten
    de forma uniforme. El primero siempre arranca en 0 y el último llega al final.
    """
    entries = []
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        term, _, at = part.partition("@")
        entries.append([term.strip(), float(at) if at.strip() else None])

    if not entries:
        return []
    total = len(entries)
    for i, entry in enumerate(entries):
        if entry[1] is None:
            entry[1] = duration * i / total
    entries[0][1] = 0.0
    entries.sort(key=lambda e: e[1])

    segments = []
    for i, (term, start) in enumerate(entries):
        end = entries[i + 1][1] if i + 1 < len(entries) else duration
        if end - start > 0.05:
            segments.append((term, start, min(end, duration)))
    return segments


def build_background_track(spec: str | None, explicit: str | None, topic: str, duration: float):
    """Un solo fondo, o una sucesión de fondos encadenados según el plan."""
    if not spec or "," not in spec:
        return build_background(pick_background(explicit, spec), topic, duration)

    from moviepy import CompositeVideoClip, concatenate_videoclips

    segments, clips, used = parse_bg_plan(spec, duration), [], set()
    for term, start, end in segments:
        path = pick_background(None, term, exclude=used)
        if path:
            used.add(path)
        log(f"{start:5.1f}-{end:5.1f}s  '{term}' -> {path.name if path else 'generado'}")
        seg = build_background(path, topic, end - start)
        # Normaliza el lienzo: los fondos con zoom crecen por encima de 1080x1920
        # y concatenate_videoclips exige que todos midan exactamente lo mismo.
        clips.append(
            CompositeVideoClip([seg], size=(WIDTH, HEIGHT)).with_duration(end - start)
        )
    return concatenate_videoclips(clips)


def gradient_image(hue: float, w: int, h: int, seed: int) -> "np.ndarray":
    """Degradado diagonal con viñeta; la paleta se deriva del tema."""
    import numpy as np

    top = colorsys.hsv_to_rgb(hue, 0.75, 0.46)
    bottom = colorsys.hsv_to_rgb((hue + 0.13) % 1.0, 0.90, 0.09)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # Rampa diagonal: menos plana que un degradado puramente vertical.
    ramp = np.clip(0.75 * (yy / h) + 0.25 * (xx / w), 0.0, 1.0)[:, :, None]
    img = (np.array(top, np.float32) * (1 - ramp) + np.array(bottom, np.float32) * ramp) * 255.0

    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    img *= np.clip(1.20 - 0.45 * d, 0.0, 1.0)[:, :, None]

    # Ruido de ±1.2 niveles: rompe el banding que deja el redondeo a uint8
    # en degradados suaves (se ve como franjas concéntricas en pantalla).
    img += np.random.default_rng(seed).uniform(-1.2, 1.2, img.shape).astype(np.float32)
    return np.clip(img, 0, 255).astype("uint8")


def _bokeh_sprite(size: int = 160):
    """Disco difuminado con un anillo exterior algo más brillante."""
    import numpy as np
    from PIL import Image

    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2.0
    d = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / c

    alpha = np.clip(1.0 - d, 0.0, 1.0) ** 1.7
    alpha += 0.30 * np.clip(1.0 - np.abs(d - 0.82) / 0.16, 0.0, 1.0)  # anillo bokeh
    alpha = np.clip(alpha, 0.0, 1.0)

    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(rgba)


def procedural_background(topic: str, duration: float):
    """
    Fondo animado: degradado + partículas bokeh que ascienden con deriva lateral.

    Se compone a media resolución y se escala al final: el bokeh es difuso, así
    que el detalle perdido no se aprecia y el render va cuatro veces más rápido.
    """
    import numpy as np
    from moviepy import VideoClip
    from PIL import Image

    rw, rh = WIDTH // 2, HEIGHT // 2
    seed = int(hashlib.md5(topic.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)

    base = Image.fromarray(gradient_image((seed % 1000) / 1000.0, rw, rh, seed)).convert("RGBA")
    sprite = _bokeh_sprite()

    particles = []
    for _ in range(26):
        radius = int(rng.integers(18, 85))
        # El sprite se pre-escala y se le fija la opacidad aquí, una sola vez:
        # hacerlo por fotograma multiplicaría el coste del render.
        s = sprite.resize((radius * 2, radius * 2), Image.LANCZOS)
        a = s.getchannel("A").point(lambda v, o=float(rng.uniform(0.10, 0.32)): int(v * o))
        s.putalpha(a)
        particles.append(
            {
                "sprite": s,
                "r": radius,
                "x": float(rng.uniform(0, rw)),
                "y": float(rng.uniform(0, rh)),
                "speed": float(rng.uniform(6, 22)),          # px/s hacia arriba
                "drift": float(rng.uniform(10, 45)),         # amplitud lateral
                "omega": float(rng.uniform(0.15, 0.55)),     # velocidad del vaivén
                "phase": float(rng.uniform(0, 6.283)),
            }
        )

    span = rh + 2 * max(p["r"] for p in particles)

    def make_frame(t):
        frame = base.copy()
        for p in particles:
            y = (p["y"] - p["speed"] * t) % span - p["r"]
            x = p["x"] + p["drift"] * math.sin(t * p["omega"] + p["phase"])
            frame.alpha_composite(p["sprite"], (int(x - p["r"]), int(y - p["r"])))
        return np.asarray(frame.convert("RGB"))

    return VideoClip(make_frame, duration=duration).resized((WIDTH, HEIGHT))


def fit_cover(clip):
    """Escala y recorta al centro para llenar 1080x1920 sin deformar."""
    scale = max(WIDTH / clip.w, HEIGHT / clip.h)
    clip = clip.resized(scale)
    return clip.cropped(
        width=WIDTH, height=HEIGHT, x_center=clip.w / 2, y_center=clip.h / 2
    )


def build_background(path: Path | None, topic: str, duration: float):
    from moviepy import ColorClip, ImageClip, VideoFileClip, concatenate_videoclips

    if path is None:
        log("Sin archivos en assets/backgrounds: generando fondo animado con bokeh")
        return procedural_background(topic, duration)

    if path.suffix.lower() in IMAGE_EXTS:
        log(f"Fondo (imagen): {path.name}")
        clip = fit_cover(ImageClip(str(path)).with_duration(duration))
        return clip.resized(lambda t: 1.0 + 0.07 * t / max(duration, 0.1)).with_position(
            ("center", "center")
        )

    log(f"Fondo (video): {path.name}")
    src = VideoFileClip(str(path)).without_audio()
    if src.duration >= duration:
        clip = src.subclipped(0, duration)
    else:
        # Repite el clip las veces necesarias para cubrir el audio.
        repeats = int(duration // src.duration) + 1
        clip = concatenate_videoclips([src] * repeats).subclipped(0, duration)
        log(f"Fondo más corto que el audio: repetido {repeats}x")
    return fit_cover(clip)


# --------------------------------------------------------------------------- #
# 5. Render
# --------------------------------------------------------------------------- #

def _text_width(text: str, font_path: str, size: int) -> int:
    from PIL import ImageFont

    f = ImageFont.truetype(font_path, size)
    box = f.getbbox(text, stroke_width=CAPTION_STROKE)
    return box[2] - box[0]


def fit_font_size(text: str, font_path: str, box_w: int) -> int:
    """Mayor tamaño de fuente con el que la palabra más larga cabe en la caja."""
    longest = max(text.split(), key=len, default=text)
    size = CAPTION_FONT_SIZE
    while size > MIN_CAPTION_FONT_SIZE:
        if _text_width(longest, font_path, size) <= box_w:
            return size
        size -= 4
    return MIN_CAPTION_FONT_SIZE


def wrap_lines(text: str, font_path: str, size: int, box_w: int) -> list[str]:
    """
    Reparte el texto en líneas midiendo con PIL, cortando solo entre palabras.

    No delegamos esto a moviepy: su __break_text (VideoClip.py) mezcla un índice
    absoluto sobre el texto completo (`last_space`) con un corte sobre la línea
    en curso, así que a partir del segundo salto parte las palabras a mitad
    ("AGOTADO" -> "AGOT" / "ADO"). Por eso usamos method="label", que respeta
    los saltos de línea que le damos ya calculados.
    """
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and _text_width(candidate, font_path, size) > box_w:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def render_caption_image(lines: list[str], font_path: str, size: int):
    """
    Dibuja el bloque de subtítulo con PIL y lo devuelve como RGBA.

    No usamos TextClip: además del wrap defectuoso, con method="label" calcula
    de menos la altura del texto multilínea con borde y recorta la última línea
    por abajo. Midiendo y dibujando aquí controlamos el lienzo exacto.
    """
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(font_path, size)
    text = "\n".join(lines)
    spacing = int(size * 0.18)

    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    # multiline_textbbox devuelve floats; Image.new exige enteros.
    bbox = [int(v) for v in probe.multiline_textbbox(
        (0, 0), text, font=font, align="center", spacing=spacing,
        stroke_width=CAPTION_STROKE,
    )]
    pad = CAPTION_STROKE * 2 + 10
    img = Image.new(
        "RGBA", (bbox[2] - bbox[0] + 2 * pad, bbox[3] - bbox[1] + 2 * pad), (0, 0, 0, 0)
    )
    ImageDraw.Draw(img).multiline_text(
        (pad - bbox[0], pad - bbox[1]), text, font=font, fill=(255, 255, 255, 255),
        stroke_width=CAPTION_STROKE, stroke_fill=(0, 0, 0, 255),
        align="center", spacing=spacing,
    )
    return np.asarray(img)


def build_caption_clips(captions: list[dict], font: str, animate: bool):
    from moviepy import ImageClip

    clips = []
    box_w = int(WIDTH * 0.86)
    band_center = int(HEIGHT * CAPTION_Y_RATIO) + CAPTION_BOX_H // 2
    shrunk = 0

    for cap in captions:
        text = cap["text"].upper()
        size = fit_font_size(text, font, box_w)
        if size < CAPTION_FONT_SIZE:
            shrunk += 1
        lines = wrap_lines(text, font, size, box_w)
        # Más de tres líneas satura la pantalla en vertical: encogemos hasta que quepa.
        while len(lines) > MAX_CAPTION_LINES and size > MIN_CAPTION_FONT_SIZE:
            size -= 4
            lines = wrap_lines(text, font, size, box_w)
        # transparent=True usa el canal alfa del RGBA como máscara del clip.
        txt = (
            ImageClip(render_caption_image(lines, font, size), transparent=True)
            .with_start(cap["start"])
            .with_duration(cap["duration"])
        )

        # Centramos el bloque en la banda: así no se desplaza según nº de líneas.
        y = band_center - txt.h // 2

        if animate and cap["duration"] > 0.2:
            # Micro "pop" de entrada: 0.90 -> 1.0 en los primeros 120 ms.
            # La condición vive fuera de la lambda: dentro capturaría la
            # duración de la última iteración del bucle, no la de este bloque.
            txt = txt.resized(lambda t: 0.90 + 0.10 * min(t / 0.12, 1.0))

        clips.append(txt.with_position(("center", y)))

    if shrunk:
        log(f"{shrunk} bloques con fuente reducida para no partir palabras largas")
    return clips


def render(background, audio_path: Path, captions: list[dict], font: str,
           out_path: Path, animate: bool, duration: float) -> None:
    from moviepy import AudioFileClip, CompositeVideoClip

    audio = AudioFileClip(str(audio_path))
    caption_clips = build_caption_clips(captions, font, animate)
    log(f"Componiendo {len(caption_clips)} bloques de subtítulos")

    video = (
        CompositeVideoClip([background, *caption_clips], size=(WIDTH, HEIGHT))
        .with_duration(duration)
        .with_audio(audio)
    )

    video.write_videofile(
        str(out_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=os.cpu_count() or 4,
        temp_audiofile=str(TMP_DIR / "temp-audio.m4a"),
    )
    video.close()
    audio.close()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Genera un Reel/Short 9:16 con voz en español y subtítulos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--topic", required=True, help="Tema del video.")
    p.add_argument("--script", help="Guion completo en texto (lo escribe Claude).")
    p.add_argument("--script-file", help="Ruta a un archivo .txt con el guion.")
    p.add_argument("--voice", default=DEFAULT_VOICE, help=f"Voz edge-tts (def: {DEFAULT_VOICE}).")
    p.add_argument("--rate", default="+8%", help="Velocidad de habla, ej. '+10%%' o '-5%%'.")
    p.add_argument("--pitch", default="+0Hz", help="Tono, ej. '+2Hz'.")
    p.add_argument("--background", help="Ruta a un fondo concreto (video o imagen).")
    p.add_argument("--bg-match",
                   help="Fondo por nombre. Varios separados por coma y con "
                        "'@segundo' opcional: 'sleeping,coffee@7.3,alarm@25.5'.")
    p.add_argument("--font", help="Ruta a un archivo .ttf para los subtítulos.")
    p.add_argument("--output", help="Ruta de salida .mp4 (por defecto outputs/video_TIMESTAMP.mp4).")
    p.add_argument("--no-anim", action="store_true", help="Desactiva la animación de subtítulos.")
    p.add_argument("--keep-audio", action="store_true", help="Conserva el .mp3 intermedio.")
    p.add_argument("--dry-run", action="store_true", help="Solo imprime el guion y termina.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    for d in (OUTPUTS_DIR, TMP_DIR, BACKGROUNDS_DIR, FONTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    total = 5
    print(f"\n=== Generando Reel: \"{args.topic}\" ===")

    # 1. Guion
    step(1, total, "Guion")
    script_text = load_script(args)
    words_n = len(script_text.split())
    # 2.7 palabras/s: ritmo medido con las voces es-* a --rate +8%.
    log(f"{words_n} palabras (~{words_n / 2.7:.0f}s estimados)")
    print(f"\n{textwrap.fill(script_text, 88)}\n")
    if args.dry_run:
        print("--dry-run activo: no se genera audio ni video.")
        return

    # 2. Voz
    step(2, total, f"Voz en español ({args.voice})")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    mp3 = TMP_DIR / f"voz_{ts}.mp3"
    word_marks = synthesize_voice(script_text, args.voice, args.rate, args.pitch, mp3)

    from moviepy import AudioFileClip
    with AudioFileClip(str(mp3)) as a:
        duration = float(a.duration)
    log(f"Duración real: {duration:.1f}s")
    if not 20 <= duration <= 60:
        log(f"AVISO: fuera del rango ideal 30-45s. Ajusta la longitud del guion o --rate.")

    # 3. Subtítulos
    step(3, total, "Subtítulos sincronizados")
    if word_marks:
        captions = group_captions(attach_punctuation(word_marks, script_text))
    else:
        log("Sin marcas de tiempo del servicio: reparto proporcional por longitud")
        captions = captions_from_text(script_text, duration)
    captions = [c for c in captions if c["start"] < duration]
    if captions:
        captions[-1]["duration"] = min(captions[-1]["duration"], duration - captions[-1]["start"])
    log(f"{len(captions)} bloques generados")

    # 4. Fondo
    step(4, total, "Fondo 1080x1920")
    bg = build_background_track(args.bg_match, args.background, args.topic, duration)

    # 5. Render
    step(5, total, "Renderizado final")
    out = Path(args.output).expanduser() if args.output else OUTPUTS_DIR / f"video_{ts}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    render(bg, mp3, captions, resolve_font(args.font), out, not args.no_anim, duration)

    if not args.keep_audio:
        mp3.unlink(missing_ok=True)

    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"\n✅ Listo: {out}")
    print(f"   {WIDTH}x{HEIGHT} · {duration:.1f}s · {size_mb:.1f} MB\n")


if __name__ == "__main__":
    main()
