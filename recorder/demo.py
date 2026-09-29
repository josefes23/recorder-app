"""
API que usan las escenas. Todo es async: cada acción se escribe con `await`.

    await d.say("Texto")                    narración; espera a que termine
    async with d.narrate("Texto"):          narración mientras ocurren acciones
        await d.click("text=Nueva tarea")
    await d.click(objetivo)                 cursor animado (escritorio) o toque (celular)
    await d.type(objetivo, "texto")         tipeo visible, letra por letra
    await d.press("Enter")
    await d.select(objetivo, "valor")
    await d.scroll(600) / d.scroll_to(obj)  desplazamiento suave
    await d.hover(objetivo)
    await d.highlight(objetivo, 1.5)        remarca un elemento
    await d.banner("Texto", 2)              cartel superior (título de sección)
    await d.wait(1.2)                       pausa en segundos
    await d.goto("/ruta")
    d.page, d.mobile, d.profile             acceso directo a Playwright

`objetivo` puede ser un selector de Playwright ("text=Guardar", "#email",
"role=button[name='Guardar']") o un Locator (d.page.get_by_role(...)).
"""

from __future__ import annotations

import asyncio
import math
import random
import time

# Centra el elemento desplazando solo su contenedor con scroll (overflow auto o
# scroll), como lo haría el usuario. scrollIntoView también mueve los ancestros
# con overflow:hidden: el layout queda corrido (desaparece la barra superior y
# se abre una franja vacía) y no hay gesto que lo devuelva a su lugar.
_CENTER_JS = """el => {
    let box = el.parentElement;
    while (box && box !== document.body) {
      const s = getComputedStyle(box);
      if (/(auto|scroll)/.test(s.overflowY) && box.scrollHeight > box.clientHeight) break;
      box = box.parentElement;
    }
    if (!box || box === document.body) box = document.scrollingElement;
    const r = el.getBoundingClientRect();
    const v = box === document.scrollingElement
      ? {top: 0, height: innerHeight} : box.getBoundingClientRect();
    box.scrollBy({top: r.top + r.height / 2 - (v.top + v.height / 2), behavior: 'smooth'});
}"""


class Narration:
    def __init__(self, demo: "Demo", text: str, audio: str | None):
        self.d, self.text, self.audio = demo, text, audio

    async def __aenter__(self):
        await self.d._voice_free.wait()          # nunca se pisan dos narraciones
        self.d._voice_free.clear()
        self.start = time.time()
        self.task = asyncio.create_task(self.d.voice.get(self.text, self.audio))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            clip = await self.task
            self.d.timeline.append({
                "text": self.text,
                "start": round(self.start - self.d.t0, 3),
                "duration": clip.duration,
                "audio": clip.path,
                "words": clip.words,
            })
            if exc_type is None:
                end = self.start + clip.duration + self.d.gap
                remaining = end - time.time()
                if remaining > 0:
                    await asyncio.sleep(remaining)
        finally:
            self.d._voice_free.set()
        return False


class Demo:
    def __init__(self, page, *, profile: str, mobile: bool, base_url: str, voice,
                 pace: float = 1.0, gap: float = 0.35):
        self.page = page
        self.profile = profile
        self.mobile = mobile
        self.base_url = base_url.rstrip("/")
        self.voice = voice
        self.pace = pace          # >1 más lento, <1 más rápido (acciones, no la voz)
        self.gap = gap            # silencio tras cada narración
        self.timeline: list[dict] = []
        self.t0 = time.time()
        self._mouse = (page.viewport_size["width"] * 0.62, page.viewport_size["height"] * 0.7)
        self._voice_free = asyncio.Event()
        self._voice_free.set()
        self.input_lock = asyncio.Lock()   # lo reemplaza el de la captura al grabar

    # ------------------------------------------------------------ voz --- #
    def narrate(self, text: str, audio: str | None = None) -> Narration:
        return Narration(self, text, audio)

    async def say(self, text: str, audio: str | None = None) -> None:
        async with self.narrate(text, audio):
            pass

    # -------------------------------------------------------- helpers --- #
    def _loc(self, target):
        return self.page.locator(target).first if isinstance(target, str) else target

    async def wait(self, seconds: float) -> None:
        await asyncio.sleep(seconds * self.pace)

    async def goto(self, path: str) -> None:
        url = path if path.startswith("http") else self.base_url + path
        await self.page.goto(url, wait_until="domcontentloaded")
        try:
            await self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        await self.wait(0.4)

    async def _ensure_visible(self, loc) -> dict:
        await loc.wait_for(state="visible", timeout=15000)
        box = await loc.bounding_box()
        vh = self.page.viewport_size["height"]
        if box is None or box["y"] < 0 or box["y"] + box["height"] > vh:
            await loc.evaluate(_CENTER_JS)
            await self.wait(0.7)
            box = await loc.bounding_box()
        return box

    async def _move_to(self, x: float, y: float) -> None:
        """Movimiento del cursor con aceleración suave (no salta de golpe)."""
        x0, y0 = self._mouse
        dist = math.hypot(x - x0, y - y0)
        if dist < 2:
            return
        duration = min(0.9, 0.25 + dist / 1400) * self.pace
        steps = max(10, int(duration * 60))
        # Leve curva para que no parezca una línea de robot.
        bend = random.uniform(-0.08, 0.08) * dist
        nx, ny = -(y - y0) / dist, (x - x0) / dist
        t_start = time.time()
        for i in range(1, steps + 1):
            t = i / steps
            e = t * t * (3 - 2 * t)                     # smoothstep
            arc = math.sin(math.pi * t) * bend
            async with self.input_lock:
                await self.page.mouse.move(x0 + (x - x0) * e + nx * arc,
                                           y0 + (y - y0) * e + ny * arc)
            target_t = t_start + duration * t
            if (rest := target_t - time.time()) > 0:
                await asyncio.sleep(rest)
        self._mouse = (x, y)

    async def _point(self, box: dict) -> tuple[float, float]:
        return (box["x"] + box["width"] * random.uniform(0.42, 0.58),
                box["y"] + box["height"] * random.uniform(0.42, 0.58))

    # -------------------------------------------------------- acciones --- #
    async def click(self, target, pause: float = 0.35) -> None:
        loc = self._loc(target)
        box = await self._ensure_visible(loc)
        x, y = await self._point(box)
        if self.mobile:
            await self.wait(0.15)
            async with self.input_lock:
                await self.page.touchscreen.tap(x, y)
        else:
            await self._move_to(x, y)
            await self.wait(0.12)
            async with self.input_lock:
                await self.page.mouse.down()
            await asyncio.sleep(0.08)
            async with self.input_lock:
                await self.page.mouse.up()
        await self.wait(pause)

    tap = click

    async def hover(self, target, pause: float = 0.4) -> None:
        loc = self._loc(target)
        box = await self._ensure_visible(loc)
        if not self.mobile:
            await self._move_to(*(await self._point(box)))
        await self.wait(pause)

    async def type(self, target, text: str, delay: float = 0.065, clear: bool = True) -> None:
        loc = self._loc(target)
        await self.click(loc, pause=0.15)
        if clear:
            await loc.fill("")
        await loc.press_sequentially(text, delay=int(delay * 1000 * self.pace))
        await self.wait(0.3)

    async def fill(self, target, text: str) -> None:
        await self._loc(target).fill(text)

    async def press(self, key: str, pause: float = 0.3) -> None:
        await self.page.keyboard.press(key)
        await self.wait(pause)

    async def select(self, target, value, pause: float = 0.4) -> None:
        loc = self._loc(target)
        await self.hover(loc, pause=0.1)
        await loc.select_option(value)
        await self.wait(pause)

    async def scroll(self, pixels: int = 500, duration: float = 0.9) -> None:
        """Desplazamiento suave de la página (o del contenedor con scroll bajo el centro)."""
        await self.page.evaluate(
            """([dy, ms]) => new Promise(done => {
                const vw = innerWidth / 2, vh = innerHeight / 2;
                let el = document.elementFromPoint(vw, vh);
                while (el && el !== document.body) {
                  const s = getComputedStyle(el);
                  if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight) break;
                  el = el.parentElement;
                }
                const box = (!el || el === document.body) ? document.scrollingElement : el;
                const y0 = box.scrollTop, t0 = performance.now();
                const step = now => {
                  const t = Math.min(1, (now - t0) / ms);
                  box.scrollTop = y0 + dy * (t < .5 ? 2*t*t : 1 - Math.pow(-2*t + 2, 2) / 2);
                  t < 1 ? requestAnimationFrame(step) : done();
                };
                requestAnimationFrame(step);
            })""",
            [pixels, int(duration * 1000 * self.pace)],
        )
        await self.wait(0.25)

    async def scroll_to(self, target) -> None:
        loc = self._loc(target)
        await loc.evaluate(_CENTER_JS)
        await self.wait(0.8)

    async def highlight(self, target, seconds: float = 1.5) -> None:
        loc = self._loc(target)
        await self._ensure_visible(loc)
        await loc.evaluate("(el, ms) => window.__demo && window.__demo.highlight(el, ms)",
                           int(seconds * 1000))
        await asyncio.sleep(seconds + 0.2)

    async def banner(self, text: str, seconds: float = 2.0, wait: bool = False) -> None:
        await self.page.evaluate("([t, ms]) => window.__demo && window.__demo.banner(t, ms)",
                                 [text, int(seconds * 1000)])
        if wait:
            await asyncio.sleep(seconds)
