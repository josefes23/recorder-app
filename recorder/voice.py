"""
Voz de la narración.

- "edge": edge-tts, gratis, con marcas de tiempo por palabra (adaptado de
  auto-video-generator). Requiere internet.
- "test": tono de prueba sin red, para verificar la instalación.
- Audio propio: say("texto", audio="voz/intro.m4a") usa tu grabación y el
  texto solo alimenta los subtítulos.

Cada frase se guarda en .cache/voz/ por hash de (voz, velocidad, tono, texto):
volver a grabar una escena no vuelve a pedir la voz al servicio.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import ff

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "voz"


@dataclass
class Clip:
    text: str
    path: str
    duration: float
    words: list[dict] = field(default_factory=list)  # [{text,start,end}] relativos al clip


class Voice:
    def __init__(self, cfg: dict):
        self.provider = cfg.get("provider", "edge")
        self.voice = cfg.get("voice", "es-MX-DaliaNeural")
        self.rate = cfg.get("rate", "+0%")
        self.pitch = cfg.get("pitch", "+0Hz")
        self._locks: dict[str, asyncio.Lock] = {}
        CACHE.mkdir(parents=True, exist_ok=True)

    async def get(self, text: str, audio: str | None = None) -> Clip:
        if audio:
            p = Path(audio)
            if not p.is_absolute():
                p = (ROOT / p).resolve()
            if not p.is_file():
                raise FileNotFoundError(f"No existe el audio {p}")
            return Clip(text, str(p), ff.duration(p), [])

        key = hashlib.sha1(
            f"{self.provider}|{self.voice}|{self.rate}|{self.pitch}|{text}".encode()
        ).hexdigest()[:16]
        mp3, meta = CACHE / f"{key}.mp3", CACHE / f"{key}.json"
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            if not (mp3.is_file() and meta.is_file()):
                if self.provider == "edge":
                    words = await self._edge(text, mp3)
                elif self.provider == "test":
                    words = await asyncio.to_thread(self._test_tone, text, mp3)
                else:
                    raise SystemExit(f"ERROR: proveedor de voz desconocido: {self.provider}")
                dur = ff.duration(mp3)
                meta.write_text(json.dumps({"duration": dur, "words": words}, ensure_ascii=False),
                                encoding="utf-8")
            data = json.loads(meta.read_text(encoding="utf-8"))
        return Clip(text, str(mp3), data["duration"], data["words"])

    async def _edge(self, text: str, mp3: Path) -> list[dict]:
        tmp = mp3.with_suffix(".part.mp3")
        last = None
        for attempt in range(3):
            try:
                words = await _edge_stream(text, self.voice, self.rate, self.pitch, tmp)
                if tmp.stat().st_size > 1024:
                    tmp.replace(mp3)
                    return words
                last = "audio vacío"
            except Exception as e:  # red intermitente: se reintenta
                last = e
            await asyncio.sleep(1.5 * (attempt + 1))
        raise SystemExit(
            f"ERROR: edge-tts no pudo generar la voz ({last}). "
            "Revisa tu conexión a internet (edge-tts necesita red)."
        )

    @staticmethod
    def _test_tone(text: str, mp3: Path) -> list[dict]:
        """Tono suave con la duración que tendría la frase (2,7 palabras/s)."""
        tokens = text.split()
        dur = max(1.0, len(tokens) / 2.7)
        ff.run(["-f", "lavfi", "-i", f"sine=frequency=330:duration={dur:.2f}",
                "-af", "volume=0.25,afade=t=in:d=0.1,afade=t=out:st=%.2f:d=0.2" % (dur - 0.2),
                "-ac", "1", "-ar", "24000", "-c:a", "libmp3lame", "-b:a", "48k", str(mp3)])
        step = dur / max(1, len(tokens))
        # Sin puntuación, como devuelve edge-tts (attach_punctuation la recupera).
        return [{"text": t.strip(".,;:?!…¡¿\"'"), "start": i * step, "end": (i + 0.9) * step}
                for i, t in enumerate(tokens)]


async def _edge_stream(text: str, voice: str, rate: str, pitch: str, out_mp3: Path) -> list[dict]:
    """Genera el mp3 y devuelve los eventos WordBoundary con tiempos reales."""
    import edge_tts

    # edge-tts 7.x emite SentenceBoundary por defecto; hace falta precisión por palabra.
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                       boundary="WordBoundary")
    words: list[dict] = []
    with open(out_mp3, "wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offset/duration vienen en unidades de 100 nanosegundos.
                words.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 1e7,
                    "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                })
    return words
