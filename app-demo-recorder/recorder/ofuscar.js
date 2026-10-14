// Blurea los datos sensibles en la página ANTES de que se capturen: emails,
// teléfonos, documentos, los datos de la cuenta con la que se graba y lo que
// pida OFUSCAR en config.py. Python reemplaza __CONFIG__.
//
// En el texto se blurea solo el tramo sensible ("Hola, <nombre> · Organizador"
// deja el resto nítido), con la API de resaltados de CSS: pinta rangos exactos
// sin tocar el DOM de React y acompaña scrolls y animaciones sin retraso. El
// tramo queda con el texto transparente y una sombra difusa del mismo tono.
// Los campos (input) y los `selectores` se blurean enteros.
(() => {
  const C = __CONFIG__;
  const ATTR = "data-demo-ofuscado";
  const textos = (C.textos || []).filter(Boolean).map(t => t.toLowerCase());
  const BASE = C.blur || 9;

  const EMAIL = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
  const DOC = /\b\d{1,2}\.?\d{3}\.?\d{3}\b|\b\d{2}-\d{8}-\d\b/g;   // DNI (7-8 cifras), CUIT
  const TEL = /\+?\d[\d\s().-]{6,}\d/g;

  // Tramos [inicio, fin) sensibles dentro de un texto.
  const tramos = s => {
    const out = [];
    if (!s || !s.trim()) return out;
    const todos = re => { for (const m of s.matchAll(re)) out.push([m.index, m.index + m[0].length]); };
    if (C.emails) todos(EMAIL);
    if (C.documentos) todos(DOC);
    if (C.telefonos) for (const m of s.matchAll(TEL)) {
      const d = m[0].replace(/\D/g, "").length;
      if (d >= 8 && d <= 15 && !/^\d{4}-\d{2}-\d{2}$/.test(m[0].trim()))   // no fechas ISO
        out.push([m.index, m.index + m[0].length]);
    }
    const low = s.toLowerCase();
    for (const t of textos) for (let i = low.indexOf(t); i >= 0; i = low.indexOf(t, i + 1))
      out.push([i, i + t.length]);
    return out;
  };
  const sensible = s => tramos(s).length > 0;

  // Un resaltado por tono de texto (sombra oscura o clara) y tamaño de letra
  // (el blur crece con la letra, para que un título también quede ilegible).
  const soportado = !!(window.CSS && CSS.highlights && window.Highlight);
  const TAMS = [[18, 1], [28, 1.6], [Infinity, 2.6]];
  const hl = {};
  let css = `[${ATTR}]{filter:blur(${BASE}px)!important}`;
  if (soportado) for (const tono of ["osc", "cla"]) TAMS.forEach(([, k], i) => {
    const nombre = `demo-ofuscar-${tono}-${i}`;
    hl[nombre] = new Highlight();
    CSS.highlights.set(nombre, hl[nombre]);
    const color = tono === "osc" ? "rgba(25,25,25,.85)" : "rgba(255,255,255,.92)";
    css += `::highlight(${nombre}){color:transparent;-webkit-text-fill-color:transparent;` +
           `text-shadow:0 0 ${Math.round(BASE * k)}px ${color},0 0 ${Math.round(BASE * k * 1.6)}px ${color}}`;
  });

  const rangos = new Map();   // nodo de texto → [[highlight, Range]]
  const quitar = n => {
    for (const [h, r] of rangos.get(n) || []) h.delete(r);
    rangos.delete(n);
  };
  const resaltado = el => {
    const s = getComputedStyle(el);
    const [r, g, b] = (s.color.match(/\d+(\.\d+)?/g) || [0, 0, 0]).map(Number);
    const tono = (0.299 * r + 0.587 * g + 0.114 * b) > 150 ? "cla" : "osc";
    const px = parseFloat(s.fontSize) || 16;
    return hl[`demo-ofuscar-${tono}-${TAMS.findIndex(([max]) => px < max)}`];
  };

  const marcar = el => {
    if (el && el.nodeType === 1 && !el.closest("#__demo-layer")) el.setAttribute(ATTR, "");
  };

  const revisarTexto = n => {
    quitar(n);
    const ts = tramos(n.nodeValue);
    if (!ts.length || !n.parentElement || n.parentElement.closest("#__demo-layer")) return;
    if (!soportado) return marcar(n.parentElement);
    const h = resaltado(n.parentElement);
    const lista = ts.map(([s, e]) => {
      const r = new Range();
      r.setStart(n, s);
      r.setEnd(n, e);
      h.add(r);
      return [h, r];
    });
    rangos.set(n, lista);
  };

  const revisar = root => {
    if (!root) return;
    if (root.nodeType === 3) return revisarTexto(root);
    if (root.nodeType !== 1 || root.id === "__demo-layer") return;
    for (const s of C.selectores || []) {
      try {
        if (root.matches(s)) marcar(root);
        root.querySelectorAll(s).forEach(marcar);
      } catch (e) { /* selector inválido: se ignora */ }
    }
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) revisarTexto(n);
    const campos = root.matches("input,textarea") ? [root] : root.querySelectorAll("input,textarea");
    campos.forEach(i => { if (sensible(i.value)) marcar(i); });
  };

  const olvidar = root => {
    if (root.nodeType === 3) return quitar(root);
    if (root.nodeType !== 1) return;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) quitar(n);
  };

  const iniciar = () => {
    const st = document.createElement("style");
    st.textContent = css;
    document.documentElement.appendChild(st);
    revisar(document.body);
    new MutationObserver(ms => {
      for (const m of ms) {
        if (m.type === "characterData") revisarTexto(m.target);
        else {
          m.removedNodes.forEach(olvidar);
          m.addedNodes.forEach(revisar);
        }
      }
    }).observe(document.documentElement, {childList: true, subtree: true, characterData: true});
    // Lo que se tipea en un campo no es un nodo de texto: se revisa al escribir.
    document.addEventListener("input", e => { if (sensible(e.target.value)) marcar(e.target); }, true);
  };

  if (document.body) iniciar();
  else document.addEventListener("DOMContentLoaded", iniciar);
})();
