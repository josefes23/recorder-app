// Capa visual que se inyecta en cada página grabada (no toca tu app).
// - Escritorio: cursor visible que sigue al mouse de Playwright.
// - Celular: círculo de "toque" donde el dedo toca la pantalla.
// - window.__demo.highlight(el) y window.__demo.banner(texto) para remarcar cosas.
(() => {
  if (window.__demo) return;
  const MODE = "__MODE__";            // "mouse" | "touch" (lo reemplaza Python)
  const ACCENT = "__ACCENT__";
  const Z = 2147483647;

  const css = `
    #__demo-layer{position:fixed;inset:0;pointer-events:none;z-index:${Z}}
    #__demo-cursor{position:fixed;width:26px;height:26px;left:0;top:0;
      transform:translate(-3px,-2px);transition:transform .05s linear;
      filter:drop-shadow(0 2px 3px rgba(0,0,0,.35));will-change:left,top}
    .__demo-ripple{position:fixed;border-radius:50%;pointer-events:none;
      border:3px solid ${ACCENT};background:${ACCENT}33;
      transform:translate(-50%,-50%) scale(.3);opacity:.95;
      animation:__demo-rip .55s ease-out forwards}
    @keyframes __demo-rip{to{transform:translate(-50%,-50%) scale(1.25);opacity:0}}
    .__demo-hl{position:fixed;border-radius:12px;pointer-events:none;
      box-shadow:0 0 0 3px ${ACCENT},0 0 0 9999px rgba(0,0,0,.35);
      transition:opacity .3s ease;opacity:0}
    #__demo-banner{position:fixed;left:50%;top:6%;transform:translate(-50%,-12px);
      background:rgba(17,17,17,.88);color:#fff;font:600 clamp(16px,2.4vw,26px)/1.25 system-ui,-apple-system,sans-serif;
      padding:.6em 1.1em;border-radius:999px;opacity:0;transition:all .35s ease;
      max-width:88vw;text-align:center;white-space:nowrap}
    #__demo-banner.on{opacity:1;transform:translate(-50%,0)}
    ${MODE === "touch" ? "::-webkit-scrollbar{display:none!important}" : ""}
  `;

  const cursorSvg = `<svg viewBox="0 0 24 24" width="26" height="26">
    <path d="M4 2 L4 19 L8.5 14.8 L11.6 21.5 L14.4 20.3 L11.3 13.7 L17.5 13.7 Z"
      fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>`;

  let layer, cursor, banner;
  let pos = { x: -40, y: -40 };
  try { pos = JSON.parse(sessionStorage.getItem("__demo_pos")) || pos; } catch (e) {}

  function mount() {
    if (layer && document.documentElement.contains(layer)) return;
    const style = document.createElement("style");
    style.textContent = css;
    document.documentElement.appendChild(style);
    layer = document.createElement("div");
    layer.id = "__demo-layer";
    document.documentElement.appendChild(layer);
    if (MODE === "mouse") {
      cursor = document.createElement("div");
      cursor.id = "__demo-cursor";
      cursor.innerHTML = cursorSvg;
      layer.appendChild(cursor);
      place();
    }
    banner = document.createElement("div");
    banner.id = "__demo-banner";
    layer.appendChild(banner);
  }

  function place() {
    if (!cursor) return;
    cursor.style.left = pos.x + "px";
    cursor.style.top = pos.y + "px";
  }

  function ripple(x, y, size) {
    mount();
    const r = document.createElement("div");
    r.className = "__demo-ripple";
    r.style.left = x + "px";
    r.style.top = y + "px";
    r.style.width = r.style.height = size + "px";
    layer.appendChild(r);
    setTimeout(() => r.remove(), 700);
  }

  addEventListener("pointermove", (e) => {
    pos = { x: e.clientX, y: e.clientY };
    try { sessionStorage.setItem("__demo_pos", JSON.stringify(pos)); } catch (err) {}
    mount(); place();
  }, true);

  addEventListener("pointerdown", (e) => {
    const touch = e.pointerType === "touch" || MODE === "touch";
    ripple(e.clientX, e.clientY, touch ? 64 : 42);
    if (cursor) cursor.style.transform = "translate(-3px,-2px) scale(.85)";
  }, true);
  addEventListener("pointerup", () => {
    if (cursor) cursor.style.transform = "translate(-3px,-2px)";
  }, true);

  window.__demo = {
    highlight(el, ms) {
      mount();
      const r = el.getBoundingClientRect();
      const pad = 6;
      const box = document.createElement("div");
      box.className = "__demo-hl";
      Object.assign(box.style, {
        left: r.left - pad + "px", top: r.top - pad + "px",
        width: r.width + pad * 2 + "px", height: r.height + pad * 2 + "px",
      });
      layer.appendChild(box);
      requestAnimationFrame(() => (box.style.opacity = "1"));
      setTimeout(() => { box.style.opacity = "0"; setTimeout(() => box.remove(), 350); }, ms);
    },
    banner(text, ms) {
      mount();
      banner.textContent = text;
      banner.classList.add("on");
      clearTimeout(banner._t);
      banner._t = setTimeout(() => banner.classList.remove("on"), ms);
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
