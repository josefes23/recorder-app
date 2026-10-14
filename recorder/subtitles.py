"""
Subtítulos y transcripción a partir de la narración.

El agrupado viene de auto-video-generator (adaptado, sin dependencia):
attach_punctuation recupera los signos que edge-tts no devuelve,
_split_sentences corta por frase y _balance reparte cada frase en bloques
parejos. Lo que cambia respecto de los Reels es el estilo: aquí son subtítulos
de landing (más texto por bloque, con puntuación y signos de apertura ¿ ¡, en
una banda discreta abajo).

Salidas: .srt, .vtt (para <track> en la web), .ass (para quemarlos en el video)
y .txt (transcripción completa, útil para SEO y accesibilidad).
"""

from __future__ import annotations

import copy
import math
import re
import textwrap
from pathlib import Path

PUNCT = ".,;:?!…"


# ---------------------------------------------------------------------- #
def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s, flags=re.UNICODE).lower()


def attach_punctuation(words: list[dict], text: str) -> list[dict]:
    """edge-tts devuelve las palabras sin puntuación: se relee el signo final de
    cada una en el guion, avanzando con una ventana de tolerancia (por si el TTS
    verbaliza cifras o abreviaturas de otra forma)."""
    tokens = re.findall(r"\S+", text)
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


def _balance(sentence: list[dict], max_chars: int, max_words: int) -> list[list[dict]]:
    """Reparte una frase en bloques de tamaño parejo (sin colas huérfanas de
    una palabra sola en pantalla)."""
    if not sentence:
        return []
    n_chars = math.ceil(len(" ".join(w["text"] for w in sentence)) / max_chars)
    n_words = math.ceil(len(sentence) / max_words)
    n = max(1, n_chars, n_words)

    base, extra = divmod(len(sentence), n)
    blocks, i = [], 0
    for b in range(n):
        size = base + (1 if b < extra else 0)
        if size:
            blocks.append(sentence[i : i + size])
            i += size
    return blocks


def _captions_from_text(text: str, duration: float, max_chars: int) -> list[dict]:
    """Respaldo si no hay marcas de tiempo (audio propio): reparto proporcional."""
    chunks = textwrap.wrap(text, width=max_chars)
    total_chars = sum(len(c) for c in chunks) or 1
    caps, t = [], 0.0
    for c in chunks:
        d = duration * len(c) / total_chars
        caps.append({"text": c, "start": t, "end": t + d})
        t += d
    return caps


def _align_display(words: list[dict], text: str) -> None:
    """Asigna a cada palabra el token original del guion (con ¿¡, tildes, cifras)."""
    tokens = re.findall(r"\S+", text)
    ti = 0
    for w in words:
        w["display"] = w["text"] + w.get("punct", "")
        target = _norm(w["text"])
        if not target:
            continue
        j, limit = ti, min(len(tokens), ti + 6)
        while j < limit and _norm(tokens[j]) != target:
            j += 1
        if j < limit:
            w["display"] = tokens[j]
            ti = j + 1


def build(timeline: list[dict], video_dur: float, max_chars: int, max_words: int) -> list[dict]:
    """Convierte la línea de tiempo de narraciones en bloques {text,start,end}."""
    caps: list[dict] = []
    for i, item in enumerate(timeline):
        start, text = item["start"], item["text"].strip()
        if not text:
            continue
        nxt = timeline[i + 1]["start"] if i + 1 < len(timeline) else video_dur
        limit = min(nxt - 0.05, video_dur)
        words = copy.deepcopy(item.get("words") or [])

        if words:
            attach_punctuation(words, text)
            _align_display(words, text)
            blocks = []
            for sentence in _split_sentences(words):
                for block in _balance(sentence, max_chars, max_words):
                    blocks.append({
                        "text": " ".join(w["display"] for w in block),
                        "start": start + block[0]["start"],
                        "end": start + block[-1]["end"],
                        # para resaltar la palabra que se está diciendo
                        "words": [{"text": w["display"], "start": start + w["start"]}
                                  for w in block],
                    })
        else:
            blocks = [{"text": c["text"], "start": start + c["start"], "end": start + c["end"]}
                      for c in _captions_from_text(text, item["duration"], max_chars)]

        # Cada bloque dura hasta el siguiente para que no parpadee en las
        # pausas; el último se sostiene un poco.
        for k, b in enumerate(blocks):
            if k + 1 < len(blocks):
                b["end"] = max(b["end"], blocks[k + 1]["start"])
            else:
                b["end"] = b["end"] + 0.5
            b["start"] = max(0.0, b["start"])
            b["end"] = min(b["end"], limit)
            if b["end"] - b["start"] >= 0.2:
                caps.append(b)
    return caps


# ---------------------------------------------------------------------- #
def _ts(t: float, sep: str) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def write_srt(caps: list[dict], path: Path) -> None:
    lines = []
    for i, c in enumerate(caps, 1):
        lines += [str(i), f"{_ts(c['start'], ',')} --> {_ts(c['end'], ',')}", c["text"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_vtt(caps: list[dict], path: Path) -> None:
    lines = ["WEBVTT", ""]
    for c in caps:
        lines += [f"{_ts(c['start'], '.')} --> {_ts(c['end'], '.')}", c["text"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_txt(timeline: list[dict], path: Path) -> None:
    path.write_text("\n\n".join(t["text"].strip() for t in timeline if t["text"].strip()) + "\n",
                    encoding="utf-8")


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def band_height(width: int, height: int, style: dict) -> int:
    """Alto de la franja inferior (modo "band"): entra hasta dos líneas."""
    font_px = round(min(width, height) * style.get("font_ratio", 0.042))
    return int(round(font_px * 3.4 / 2) * 2)   # par, para yuv420p


def write_ass(caps: list[dict], path: Path, width: int, height: int, style: dict) -> None:
    """ASS con PlayRes = resolución real: tamaños en píxeles exactos.

    placement "overlay": caja semitransparente sobre el video.
    placement "band":    franja sólida agregada debajo del video (height ya la
                         incluye); los subtítulos nunca tapan la interfaz.
    """
    short = min(width, height)
    font_px = round(short * style.get("font_ratio", 0.042))
    margin_h = round(width * 0.06)
    font = style.get("font", "Arial")
    bold = -1 if style.get("bold", True) else 0

    if style.get("placement") == "band":
        band = band_height(width, height - band_height(width, height, style), style)
        align, border, outline = 5, 1, 0          # centrado en la franja
        margin_v = 0
        # Centrado vertical en la franja con \pos: x al medio, y al medio de la banda.
        pos = f"\\an5\\pos({width // 2},{height - band // 2})"
        prim, back = "&H00FFFFFF", "&H00000000"
    else:
        pad = max(6, round(font_px * 0.32))
        alpha = style.get("box_alpha", "50")  # 00 opaco … FF transparente
        align = 8 if style.get("position") == "top" else 2
        border, outline = 3, pad
        margin_v = round(height * style.get("margin_bottom", 0.08))
        pos = ""
        prim, back = "&H00FFFFFF", f"&H{alpha}111111"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_px},{prim},{prim},{back},{back},{bold},0,0,0,100,100,0,0,{border},{outline},0,{align},{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def esc(s: str) -> str:
        return s.replace("\n", " ").replace("{", "(").replace("}", ")")

    hl = _ass_color(style.get("highlight", "#FFD54A"))
    events = []
    for c in caps:
        palabras, activa = c.get("palabras"), c.get("activa")
        if palabras is None or activa is None:
            text = esc(c["text"])
        else:
            text = " ".join(f"{{\\c{hl}}}{esc(p)}{{\\c&HFFFFFF&}}" if i == activa else esc(p)
                            for i, p in enumerate(palabras))
        # Con karaoke, el bloque aparece y se va con fundido; los estados del medio, no.
        fad = f"\\fad({120 if c.get('primero', True) else 0},{120 if c.get('ultimo', True) else 0})"
        events.append(f"Dialogue: 0,{_ass_time(c['start'])},{_ass_time(c['end'])},Default,,0,0,0,,"
                      f"{{{pos}{fad}}}{text}")
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def estados(caps: list[dict]) -> list[dict]:
    """Subtítulos animados: un estado por palabra, con la que se está diciendo
    resaltada. Los bloques sin tiempos por palabra (voz grabada) quedan igual."""
    out = []
    for c in caps:
        ws = c.get("words")
        if not ws:
            out.append(c)
            continue
        palabras = [w["text"] for w in ws]
        for j, w in enumerate(ws):
            s = c["start"] if j == 0 else max(w["start"], c["start"])
            e = min(ws[j + 1]["start"], c["end"]) if j + 1 < len(ws) else c["end"]
            if e - s >= 0.02:
                out.append({"text": c["text"], "palabras": palabras, "activa": j,
                            "start": s, "end": e, "primero": j == 0, "ultimo": j + 1 == len(ws)})
    return out


def _ass_color(hex_: str) -> str:
    h = hex_.lstrip("#")
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def write_images(caps: list[dict], folder: Path, width: int, height: int, band: int,
                 style: dict, fonts_dir: Path) -> list[dict]:
    """Sin libass: cada bloque como PNG transparente para superponer con el
    filtro overlay, que tiene cualquier ffmpeg. Misma geometría que write_ass
    (height es el del video, sin la franja). Devuelve [{png, start, end, x, y}]."""
    from PIL import Image, ImageDraw, ImageFont

    total = height + band
    font_px = round(min(width, total) * style.get("font_ratio", 0.042))
    font = _pil_font(ImageFont, style, font_px, fonts_dir)
    max_w = width - 2 * round(width * 0.06)
    line_h = round(font_px * 1.25)
    in_band = style.get("placement") == "band"
    pad = 0 if in_band else max(6, round(font_px * 0.32))
    opacity = 255 - int(style.get("box_alpha", "50"), 16)   # alfa ASS: 00 opaco … FF transparente

    h_rgb = style.get("highlight", "#FFD54A").lstrip("#")
    resaltado = tuple(int(h_rgb[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    blanco = (255, 255, 255, 255)
    space = font.getlength(" ")

    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for i, c in enumerate(caps):
        palabras = c.get("palabras") or c["text"].replace("\n", " ").split() or [""]
        activa = c.get("activa")
        lines = _wrap(palabras, font, max_w)
        text_w = max(round(font.getlength(" ".join(palabras[k] for k in ln))) for ln in lines)
        w, h = text_w + 2 * pad, line_h * len(lines) + 2 * pad
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        if not in_band:
            draw.rectangle([0, 0, w, h], fill=(17, 17, 17, opacity))
        for n, ln in enumerate(lines):
            x = (w - font.getlength(" ".join(palabras[k] for k in ln))) / 2
            for k in ln:                       # palabra por palabra: la que se dice, resaltada
                draw.text((x, pad + line_h * n + line_h / 2), palabras[k], font=font,
                          fill=resaltado if k == activa else blanco, anchor="lm")
                x += font.getlength(palabras[k]) + space
        png = folder / f"{i:03d}.png"
        img.save(png)
        if in_band:                                    # centrado en la franja
            y = height + (band - h) // 2
        elif style.get("position") == "top":
            y = round(total * style.get("margin_bottom", 0.08))
        else:
            y = total - round(total * style.get("margin_bottom", 0.08)) - h
        out.append({"png": png, "start": c["start"], "end": c["end"],
                    "x": (width - w) // 2, "y": y})
    return out


def _pil_font(ImageFont, style: dict, size: int, fonts_dir: Path):
    """La fuente de fonts/ ("Liberation Sans" → LiberationSans-Bold.ttf)."""
    family = style.get("font", "").replace(" ", "")
    weight = "Bold" if style.get("bold", True) else "Regular"
    for f in (fonts_dir / f"{family}-{weight}.ttf", fonts_dir / f"{family}-Regular.ttf"):
        if f.is_file():
            return ImageFont.truetype(str(f), size)
    try:
        return ImageFont.truetype(style.get("font", "Arial"), size)   # fuente del sistema
    except OSError:
        return ImageFont.load_default(size=size)


def _wrap(palabras: list[str], font, max_w: int) -> list[list[int]]:
    """Reparte las palabras en líneas que entren en max_w (índices de palabra)."""
    lines, cur = [], []
    for k, word in enumerate(palabras):
        cand = " ".join(palabras[j] for j in cur + [k])
        if cur and font.getlength(cand) > max_w:
            lines.append(cur)
            cur = [k]
        else:
            cur.append(k)
    return lines + [cur] if cur else lines or [[0]]
