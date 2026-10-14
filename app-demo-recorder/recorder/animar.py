"""
Animaciones de postproducción, cuadro por cuadro con Pillow. Parten de la
grabación cruda y de la línea de tiempo, así que --remezclar las rehace sin
volver a grabar:

- zoom a la acción: se acerca a cada toque, tipeo o resaltado (lo que anotan
  las acciones de d.) y vuelve a la pantalla completa. El recorte es subpíxel:
  el zoompan de ffmpeg redondea a píxeles enteros y la imagen tiembla;
- transiciones: cuando la pantalla cambia de golpe, el cuadro anterior se
  funde con los siguientes. La línea de tiempo no se corre: voz, subtítulos y
  acciones siguen sincronizados;
- intro y cierre: placas con el ícono de la marca, el título de la escena y la
  llamada a la acción, que se funden con el primer y el último cuadro.

ffmpeg solo decodifica y codifica: los cuadros pasan por un pipe de RGB crudo.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

from . import ff

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
# Diferencia media (0–1) entre dos cuadros que cuenta como cambio de pantalla.
# Medido: cambiar de pantalla da 0.10–0.72; un desplazamiento, 0.04–0.07.
CORTE = 0.09
FUNDIDO_PLACA = 0.35


# Por defecto: intro y cierre con la marca siempre; zoom solo donde hace falta.
# config.py los ajusta (ANIMACIONES, MARCA); 0 apaga cada uno.
DEFECTO = {
    "zoom": {"mobile": 1.25, "desktop": 1.5},
    # Se acerca solo si alrededor del toque hay al menos `vecinos` controles
    # (zona cargada, confusa) o si el objetivo ocupa menos de `area` de la pantalla.
    "zoom_si": {"vecinos": 6, "area": 0.002},
    "transicion": 0.35,
    "subtitulos_palabra": True,
    "intro": 1.8,
    "cierre": 2.6,
}
MARCA_DEFECTO = {"icono": "marca/icono.png", "nombre": "", "color": "#1a6e3c",
                 "color_oscuro": "#0f3d22", "cierre": "", "cierre_sub": ""}


def ajustes(cfg: dict) -> tuple[dict, dict]:
    return ({**DEFECTO, **(cfg.get("ANIMACIONES") or {})},
            {**MARCA_DEFECTO, **(cfg.get("MARCA") or {})})


def activo(anim: dict) -> bool:
    zoom = anim.get("zoom") or {}
    return (any(z > 1 for z in zoom.values()) if isinstance(zoom, dict) else zoom > 1) or \
        anim.get("transicion", 0) > 0 or anim.get("intro", 0) > 0 or anim.get("cierre", 0) > 0


def _ease(x: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, x)))


# ---------------------------------------------------------------------- #
def _vale_zoom(e: dict, reglas: dict) -> bool:
    """¿Esta acción necesita zoom? Lo forzado en la escena manda; si no, solo
    en zonas con muchos controles juntos o con objetivos muy chicos."""
    if "zoom" in e:
        return bool(e["zoom"])
    chico = e.get("area", 1.0) <= reglas.get("area", 0)
    if e["kind"] == "highlight":
        return chico            # el resaltado ya oscurece el resto
    return chico or e.get("vecinos", 0) >= reglas.get("vecinos", 99)


class Zoom:
    """Curva de zoom y foco a partir de las acciones anotadas por Demo."""

    LEAD, HOLD, RAMP, PAN = 0.8, 2.0, 0.8, 0.8   # segundos: movimientos lentos, sin mareo
    UNIR = 1.2       # dos zooms a menos de esto se unen: se queda cerca en vez de ir y volver
    MIN_QUIETO = 0.8  # un zoom que no llega a quedarse quieto esto, no se hace (rebota)

    def __init__(self, events: list[dict], viewport: dict | None, W: int, H: int, zmax: float,
                 reglas: dict | None = None):
        self.W, self.H = W, H
        sx = W / viewport["width"] if viewport else 1.0
        reglas = reglas or DEFECTO["zoom_si"]
        acciones = ("click", "type", "highlight")
        # Desplazarse, navegar o una acción sin zoom: hay que estar alejado.
        breaks = sorted(e["t"] for e in events if e["kind"] in ("scroll", "nav")
                        or (e["kind"] in acciones and not _vale_zoom(e, reglas)))
        pts = []
        for e in events:
            if e["kind"] not in acciones or not _vale_zoom(e, reglas):
                continue
            z = zmax
            if e["kind"] == "highlight" and e.get("w"):
                # que el elemento resaltado entre entero
                z = min(zmax, 0.8 * W / (e["w"] * sx), 0.8 * H / (e["h"] * sx))
            pts.append((e["t"], e["x"] * sx, e["y"] * sx, max(1.0, z)))

        segs: list[list[float]] = []   # [inicio, fin, zoom, última acción]
        for t, _, _, z in pts:
            corte = max((b for b in breaks if b <= t), default=-1.0)
            a, b = max(t - self.LEAD, corte), t + self.HOLD
            if segs and a <= segs[-1][1] + self.UNIR and segs[-1][3] >= corte:
                s = segs[-1]
                s[1], s[2], s[3] = max(s[1], b), min(s[2], z), t
            else:
                segs.append([a, b, z, t])
        for k, s in enumerate(segs):
            # alejado antes de desplazarse o de una acción sin zoom (el
            # cursor ya viaja hacia ella con la pantalla completa)
            s[1] = min([s[1]] + [b - 0.2 for b in breaks if s[3] < b])
            if k:
                s[0] = max(s[0], segs[k - 1][1])
        self.segs = [(a, b, z) for a, b, z, _ in segs
                     if z > 1.001 and b - a >= 2 * self.RAMP + self.MIN_QUIETO]
        self.keys = [(t, x, y) for t, x, y, _ in pts]

    def at(self, t: float) -> tuple[float, float, float]:
        z = 1.0
        for a, b, zz in self.segs:
            e = min((t - a) / self.RAMP, (b - t) / self.RAMP)
            if e > 0:
                z += (zz - 1) * _ease(e)
        if not self.keys:
            return z, self.W / 2, self.H / 2
        fx, fy = self.keys[0][1], self.keys[0][2]
        for (_, x0, y0), (t1, x1, y1) in zip(self.keys, self.keys[1:]):
            k = _ease((t - (t1 - self.PAN)) / self.PAN)   # llega al foco nuevo con la acción
            fx, fy = fx + (x1 - x0) * k, fy + (y1 - y0) * k
        return z, fx, fy

    def apply(self, img, t: float):
        z, fx, fy = self.at(t)
        if z <= 1.001:
            return img
        from PIL import Image
        bw, bh = self.W / z, self.H / z
        x0 = min(max(fx - bw / 2, 0), self.W - bw)
        y0 = min(max(fy - bh / 2, 0), self.H - bh)
        return img.resize((self.W, self.H), Image.BICUBIC, box=(x0, y0, x0 + bw, y0 + bh))


# ---------------------------------------------------------------------- #
class Placa:
    """Placa de intro o cierre: ícono, título y subtítulo sobre el color de la marca."""

    def __init__(self, W: int, H: int, marca: dict, titulo: str, sub: str, fonts: Path):
        from PIL import Image, ImageDraw, ImageFont
        self.W, self.H = W, H
        base = min(W, H)
        c1, c2 = _rgb(marca.get("color", "#1a6e3c")), _rgb(marca.get("color_oscuro", "#0f3d22"))
        self.fondo = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(self.fondo)
        for y in range(H):                                   # degradé vertical
            k = y / max(1, H - 1)
            draw.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(c1, c2)))

        icono = ROOT / marca.get("icono", "marca/icono.png")
        lado = round(base * 0.26)
        self.icono = (Image.open(icono).convert("RGBA").resize((lado, lado), Image.LANCZOS)
                      if icono.is_file() else None)

        def fuente(peso: str, px: int):
            f = fonts / f"LiberationSans-{peso}.ttf"
            return ImageFont.truetype(str(f), px) if f.is_file() else ImageFont.load_default(size=px)

        self.textos = []   # (capa RGBA, y)
        f_tit, f_sub = fuente("Bold", round(base * 0.064)), fuente("Regular", round(base * 0.036))
        bloques = [(t, f_tit, (255, 255, 255)) for t in _lineas(titulo, f_tit, W * 0.84)]
        if sub:
            bloques += [(t, f_sub, _rgb(marca.get("color_texto_suave", "#cdebd8")))
                        for t in _lineas(sub, f_sub, W * 0.84)]
        gap = round(base * 0.05)
        alto = (lado if self.icono else 0) + gap + sum(round(f.size * 1.3) for _, f, _ in bloques)
        y = (H - alto) // 2
        self.y_icono = y
        y += (lado if self.icono else 0) + gap
        for texto, f, color in bloques:
            h = round(f.size * 1.3)
            capa = Image.new("RGBA", (W, h), (0, 0, 0, 0))
            ImageDraw.Draw(capa).text((W / 2, h / 2), texto, font=f, fill=color + (255,), anchor="mm")
            self.textos.append((capa, y))
            y += h

    def frame(self, t: float, dur: float, desde=None, hacia=None):
        """desde: cuadro que se funde hacia la placa al empezar; hacia: cuadro al
        que la placa se funde al terminar."""
        from PIL import Image
        img = self.fondo.copy()
        if self.icono:
            k = _ease(t / 0.45)
            lado = max(1, round(self.icono.width * (0.82 + 0.18 * k)))
            ic = self.icono.resize((lado, lado), Image.LANCZOS)
            _pegar(img, ic, ((self.W - lado) // 2, self.y_icono + (self.icono.height - lado) // 2), k)
        for n, (capa, y) in enumerate(self.textos):
            k = _ease((t - 0.15 - 0.08 * n) / 0.4)
            _pegar(img, capa, (0, y + round((1 - k) * self.H * 0.02)), k)
        if desde is not None and t < FUNDIDO_PLACA:
            img = Image.blend(desde, img, _ease(t / FUNDIDO_PLACA))
        if hacia is not None and t > dur - FUNDIDO_PLACA:
            img = Image.blend(img, hacia, _ease((t - (dur - FUNDIDO_PLACA)) / FUNDIDO_PLACA))
        return img


def _pegar(img, capa, pos, alfa: float) -> None:
    if alfa <= 0:
        return
    if alfa < 1:
        capa = capa.copy()
        capa.putalpha(capa.getchannel("A").point(lambda v: round(v * alfa)))
    img.paste(capa, pos, capa)


def _lineas(texto: str, font, max_w: float) -> list[str]:
    lineas, cur = [], ""
    for p in texto.split():
        cand = f"{cur} {p}".strip()
        if cur and font.getlength(cand) > max_w:
            lineas.append(cur)
            cur = p
        else:
            cur = cand
    return lineas + [cur] if cur else lineas


def _rgb(hex_: str) -> tuple[int, int, int]:
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------- #
def componer(raw: Path, trim: float, dur: float, out: Path, data: dict, cfg: dict,
             title: str) -> dict:
    """Escribe `out` (video sin audio) con las animaciones. Devuelve la duración
    de la intro (lo que se corren voz y subtítulos) y la total."""
    from PIL import Image, ImageChops, ImageStat

    anim, marca = ajustes(cfg)
    W, H = ff.size(raw)
    zcfg = anim.get("zoom", 1.0)
    zmax = zcfg.get(data["profile"], 1.0) if isinstance(zcfg, dict) else float(zcfg)
    zoom = Zoom(data.get("events", []), data.get("viewport"), W, H, zmax, anim.get("zoom_si"))
    d_tr = float(anim.get("transicion", 0))
    intro_s, cierre_s = float(anim.get("intro", 0)), float(anim.get("cierre", 0))
    fonts = ROOT / "fonts"

    dec = subprocess.Popen(
        [ff.need("ffmpeg"), "-v", "error", "-ss", f"{trim:.3f}", "-i", str(raw), "-t", f"{dur:.3f}",
         "-vf", f"fps={FPS},format=rgb24", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(
        [ff.need("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "14", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    size = W * H * 3

    def leer():
        buf = dec.stdout.read(size)
        return Image.frombytes("RGB", (W, H), buf) if len(buf) == size else None

    n_main = 0
    try:
        actual = leer()
        if actual is None:
            raise RuntimeError("no se pudo leer la grabación")
        primero = zoom.apply(actual, 0.0)

        if intro_s > 0:
            placa = Placa(W, H, marca, title, marca.get("nombre", ""), fonts)
            for i in range(round(intro_s * FPS)):
                enc.stdin.write(placa.frame(i / FPS, intro_s, hacia=primero).tobytes())

        prev_small = frozen = previo = None
        corte_t, ultimo = -9.0, primero
        while actual is not None:
            t = n_main / FPS
            small = actual.convert("L").resize((96, 60))
            if d_tr > 0 and prev_small is not None and t > 0.3 and t - corte_t > max(0.8, d_tr):
                diff = ImageStat.Stat(ImageChops.difference(small, prev_small)).mean[0] / 255
                if diff > CORTE:
                    corte_t, frozen = t, previo
            img = actual
            if frozen is not None and t - corte_t < d_tr:
                img = Image.blend(frozen, actual, _ease((t - corte_t) / d_tr))
            ultimo = zoom.apply(img, t)
            enc.stdin.write(ultimo.tobytes())
            prev_small, previo = small, actual
            n_main += 1
            actual = leer()

        if cierre_s > 0:
            placa = Placa(W, H, marca, marca.get("cierre", ""), marca.get("cierre_sub", ""), fonts)
            for i in range(round(cierre_s * FPS)):
                enc.stdin.write(placa.frame(i / FPS, cierre_s, desde=ultimo).tobytes())
    finally:
        enc.stdin.close()
        enc.wait()
        dec.stdout.close()
        dec.wait()
    if enc.returncode != 0:
        raise RuntimeError("ffmpeg no pudo codificar el video animado")
    main = n_main / FPS
    return {"intro": round(intro_s * FPS) / FPS if intro_s > 0 else 0.0,
            "total": (round(intro_s * FPS) + n_main + round(cierre_s * FPS)) / FPS,
            "main": main}
