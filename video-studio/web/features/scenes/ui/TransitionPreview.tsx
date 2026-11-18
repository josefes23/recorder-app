"use client";

import { useEffect, useRef, useState } from "react";

import { look, type Look, type Transition } from "@/domain/transition";

/** Lo que se queda quieto cada imagen antes y después del cambio, para entenderlo. */
const HOLD_SECONDS = 0.8;
/** El encuadre cerrado de una imagen fija, como el render (`domain/motion.py`). */
const CLOSE_UP = 1.18;

type Props = {
  /** La imagen de la que sale; null, negro. */
  from: string | null;
  /** La imagen a la que entra; null, negro. */
  to: string | null;
  transition: Transition;
  /** Vertical u horizontal: la miniatura toma la forma del video. */
  wide?: boolean;
  /**
   * Es un cambio de encuadre de la misma imagen (la primera escena): la de
   * llegada se ve más cerrada, como el plano siguiente del render.
   */
  reframe?: boolean;
};

function paint(layer: HTMLSpanElement | null, scale: number, shift: number, gain: number, opacity: number) {
  if (!layer) return;
  layer.style.transform = `translateX(${shift * 100}%) scale(${scale})`;
  layer.style.filter = gain < 1 ? `brightness(${gain})` : "";
  layer.style.opacity = String(opacity);
}

function apply(out: HTMLSpanElement | null, into: HTMLSpanElement | null, l: Look, base: number) {
  const push = l.push ?? 0;
  paint(out, l.zoomOut, -push, l.gainOut, 1);
  paint(into, l.zoomIn * base, l.push === null ? 0 : 1 - push, l.gainIn, l.push === null ? l.alpha : 1);
}

/**
 * La transición en pequeño, con la misma cuenta que el render: las dos
 * imágenes se mezclan en el navegador, sin pedir nada al servidor. Se repite
 * sola; con «reducir movimiento» activado, solo al pulsarla.
 */
export function TransitionPreview({ from, to, transition, wide = false, reframe = false }: Props) {
  const outRef = useRef<HTMLSpanElement>(null);
  const inRef = useRef<HTMLSpanElement>(null);
  // No cambia lo que se pinta en el HTML, así que leerlo al montar no descuadra la hidratación.
  const [still] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [plays, setPlays] = useState(0);

  useEffect(() => {
    const base = reframe ? CLOSE_UP : 1;
    const seconds = transition.kind === "corte" ? 0 : transition.seconds;
    const cycle = HOLD_SECONDS * 2 + seconds;
    // Quieta: la imagen de llegada, sin animar hasta que se pulse.
    if (still && plays === 0) {
      apply(outRef.current, inRef.current, look(transition.kind, 1), base);
      return;
    }
    let frame = 0;
    const began = performance.now();
    const tick = (now: number) => {
      const elapsed = (now - began) / 1000;
      if (still && elapsed > cycle) return; // una vuelta y se para
      const t = elapsed % cycle;
      const progress = t < HOLD_SECONDS ? 0 : seconds > 0 ? (t - HOLD_SECONDS) / seconds : 1;
      apply(outRef.current, inRef.current, look(transition.kind, progress), base);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [transition.kind, transition.seconds, reframe, still, plays]);

  return (
    <button
      type="button"
      className={`tp${wide ? " tp--wide" : ""}`}
      onClick={() => setPlays((n) => n + 1)}
      title="Vista previa de la transición. Pulsa para verla otra vez."
      aria-label="Vista previa de la transición"
    >
      {/* Sin imagen, la capa queda en negro: el fondo del recuadro. */}
      <span className="tp-layer" ref={outRef}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {from && <img src={from} alt="" />}
      </span>
      <span className="tp-layer" ref={inRef}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {to && <img src={to} alt="" />}
      </span>
    </button>
  );
}
