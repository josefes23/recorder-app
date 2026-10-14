"""
Captura de video en alta calidad.

Por qué no se usa `record_video_dir` de Playwright: graba a resolución CSS
(ignora el device_scale_factor) y a ~40 kbps, así que el texto de un celular
sale chico y borroso. En su lugar:

- "screencast"  → Page.startScreencast (hasta 60 cps). Solo entrega píxeles CSS,
                  así que sirve cuando scale == 1 (escritorio 1440x900, 1920x1080).
- "screenshot"  → Page.captureScreenshot en bucle. Respeta la densidad retina
                  (celular 390x844 @2x → 780x1688) a costa de menos cuadros
                  por segundo (15–30 según la máquina).

En ambos casos cada cuadro llega con su hora real y se reescribe a 30 fps
constantes: si un cuadro tarda, el anterior se repite. Así el reloj del video
coincide con time.time() y la voz queda sincronizada con las acciones.
"""

from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path

from . import ff

FPS = 30


class Capture:
    def __init__(self, page, context, out_path: Path, *, mode: str, width: int,
                 height: int, scale: float, mobile: bool, quality: int = 85):
        self.page = page
        self.context = context
        self.out_path = out_path
        self.mode = mode
        self.width, self.height, self.scale, self.mobile = width, height, scale, mobile
        self.quality = quality
        self.t0 = 0.0
        self.t_end = 0.0
        self.frames_in = 0
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=240)
        self._running = False
        # Mientras captureScreenshot está en vuelo Chromium remapea las
        # coordenadas de entrada: un toque en ese instante cae en otro lugar.
        # Las acciones de Demo toman este candado para despachar toques/clics.
        self.input_lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    async def start(self) -> float:
        self.cdp = await self.context.new_cdp_session(self.page)
        self.proc = await asyncio.create_subprocess_exec(
            ff.need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-r", str(FPS),
            str(self.out_path),
            stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        self._running = True
        self.t0 = time.time()
        self._writer = asyncio.create_task(self._write_loop())

        if self.mode == "screencast":
            self.cdp.on("Page.screencastFrame", self._on_frame)
            await self.cdp.send("Page.startScreencast", {
                "format": "jpeg", "quality": self.quality,
                "maxWidth": int(self.width * self.scale),
                "maxHeight": int(self.height * self.scale),
            })
        else:
            # Las métricas se fijan también en esta sesión: sin esto
            # captureScreenshot devuelve píxeles CSS (baja resolución).
            await self.cdp.send("Emulation.setDeviceMetricsOverride", {
                "width": self.width, "height": self.height,
                "deviceScaleFactor": self.scale, "mobile": self.mobile,
            })
            self._grabber = asyncio.create_task(self._screenshot_loop())
        return self.t0

    async def stop(self) -> float:
        self.t_end = time.time()
        self._running = False
        if self.mode == "screencast":
            try:
                await self.cdp.send("Page.stopScreencast")
            except Exception:
                pass
        else:
            await self._grabber
        await self._queue.put(None)
        await self._writer
        self.proc.stdin.close()
        err = await self.proc.stderr.read()
        code = await self.proc.wait()
        if code != 0:
            raise RuntimeError(f"ffmpeg (captura) falló: {err.decode(errors='replace')[-800:]}")
        if self.frames_in == 0:
            raise RuntimeError("No se capturó ningún cuadro de la página.")
        return self.t_end

    # ------------------------------------------------------------------ #
    def _on_frame(self, ev: dict) -> None:
        asyncio.create_task(
            self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
        )
        if not self._running:
            return
        ts = ev.get("metadata", {}).get("timestamp") or time.time()
        try:
            self._queue.put_nowait((ts, base64.b64decode(ev["data"])))
        except asyncio.QueueFull:
            pass  # si el codificador va atrasado, se descarta: se repetirá el anterior

    async def _screenshot_loop(self) -> None:
        # Sin optimizeForSpeed: con él, después de una navegación (d.goto) Chromium
        # deja de responder captureScreenshot y la grabación se cuelga en stop().
        params = {"format": "jpeg", "quality": self.quality}
        while self._running:
            t_req = time.time()
            try:
                async with self.input_lock:
                    r = await self.cdp.send("Page.captureScreenshot", params)
            except Exception:
                # Navegación en curso: el documento no está listo, se reintenta.
                await asyncio.sleep(0.02)
                continue
            t_resp = time.time()
            await self._queue.put(((t_req + t_resp) / 2, base64.b64decode(r["data"])))

    async def _write_loop(self) -> None:
        prev: bytes | None = None
        k = 0
        stdin = self.proc.stdin

        async def emit(data: bytes, until: float):
            nonlocal k
            while self.t0 + k / FPS <= until:
                stdin.write(data)
                k += 1
                await stdin.drain()

        while True:
            item = await self._queue.get()
            if item is None:
                break
            ts, data = item
            self.frames_in += 1
            # Cada ranura de 1/30 s muestra el último cuadro llegado antes que ella.
            await emit(prev if prev is not None else data, ts)
            prev = data
        if prev is not None:
            await emit(prev, self.t_end)
