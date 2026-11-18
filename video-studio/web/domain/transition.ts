/**
 * Transiciones: cómo entra cada escena y cómo cambia de encuadre su imagen fija.
 *
 * El video tiene una por defecto (en la producción) y cada escena puede elegir
 * la suya. Se centran en el corte: la imagen nueva sigue entrando cuando la
 * voz dice su frase. Las mismas reglas viven en `app/domain/transition.py`.
 */

export type TransitionKind = "corte" | "fundido" | "negro" | "deslizar" | "zoom";

export type Transition = { kind: TransitionKind; seconds: number };

export const TRANSITIONS: { id: TransitionKind; label: string; hint: string }[] = [
  { id: "corte", label: "Corte", hint: "Cambia de golpe, sin transición." },
  { id: "fundido", label: "Fundido encadenado", hint: "La imagen anterior se disuelve en la nueva." },
  { id: "negro", label: "Fundido a negro", hint: "Baja a negro y sube con la imagen nueva." },
  { id: "deslizar", label: "Deslizar", hint: "La nueva entra por la derecha y empuja a la anterior." },
  { id: "zoom", label: "Zoom de entrada", hint: "Un acercamiento rápido lleva de una imagen a la otra." },
];

export const MIN_TRANSITION_SECONDS = 0.2;
export const MAX_TRANSITION_SECONDS = 1.5;
export const TRANSITION_STEP = 0.1;

/** Hasta que el usuario elija otra, el corte seco de siempre. */
export const DEFAULT_TRANSITION: Transition = { kind: "corte", seconds: 0.5 };

export const isTransitionKind = (value: unknown): value is TransitionKind =>
  TRANSITIONS.some((t) => t.id === value);

/** Dentro de los límites y en décimas, como el deslizador: lo que el servidor acepta. */
export const clampSeconds = (seconds: number): number =>
  Math.min(
    MAX_TRANSITION_SECONDS,
    Math.max(MIN_TRANSITION_SECONDS, Math.round((Number.isFinite(seconds) ? seconds : DEFAULT_TRANSITION.seconds) * 10) / 10),
  );

/** La guardada con un video o una escena; null si no hay o no vale. */
export function readTransition(raw: unknown): Transition | null {
  if (!raw || typeof raw !== "object") return null;
  const { kind, seconds } = raw as Record<string, unknown>;
  if (!isTransitionKind(kind)) return null;
  return { kind, seconds: clampSeconds(typeof seconds === "number" ? seconds : DEFAULT_TRANSITION.seconds) };
}

export const transitionLabel = (kind: TransitionKind): string =>
  (TRANSITIONS.find((t) => t.id === kind) ?? TRANSITIONS[0]).label;

/** «Fundido encadenado · 0,5 s», o «Corte», que no dura. */
export const describeTransition = (transition: Transition): string =>
  transition.kind === "corte"
    ? transitionLabel("corte")
    : `${transitionLabel(transition.kind)} · ${transition.seconds.toLocaleString("es", { minimumFractionDigits: 1 })} s`;

// --------------------------------------------------------------------------- //
// Cuándo cambia y cómo se ve: la misma cuenta que `app/domain/transition.py`,
// para que la vista previa y la animática enseñen lo que va a salir.
// --------------------------------------------------------------------------- //

export type Change = { at: number; kind: TransitionKind; seconds: number };

export const changeStart = (change: Change) => change.at - change.seconds / 2;
export const changeEnd = (change: Change) => change.at + change.seconds / 2;

/**
 * Los cambios entre planos consecutivos: `bounds` son los límites (n + 1 para
 * n planos) y `entries[i]` es cómo entra el plano i + 1. Ninguna dura más que
 * los planos que une, así que dos seguidas no se pisan.
 */
export function planChanges(bounds: number[], entries: Transition[]): Change[] {
  return entries.map((transition, i) => {
    const at = bounds[i + 1];
    if (transition.kind === "corte") return { at, kind: "corte", seconds: 0 };
    const room = Math.min(at - bounds[i], bounds[i + 2] - at);
    return { at, kind: transition.kind, seconds: Math.max(0, Math.min(transition.seconds, room)) };
  });
}

/** Qué plano se ve en `t` y, si está cambiando, hacia dónde va el cambio (0 → 1). */
export function moment(changes: Change[], t: number): { index: number; kind: TransitionKind; progress: number | null } {
  for (let i = 0; i < changes.length; i++) {
    const change = changes[i];
    if (t < changeStart(change)) return { index: i, kind: change.kind, progress: null };
    if (t < changeEnd(change)) {
      return { index: i, kind: change.kind, progress: (t - changeStart(change)) / change.seconds };
    }
  }
  return { index: changes.length, kind: "corte", progress: null };
}

/** Cómo se ve cada plano en un instante del cambio. */
export type Look = {
  /** Opacidad del que entra, encima del que sale. */
  alpha: number;
  gainOut: number;
  gainIn: number;
  zoomOut: number;
  zoomIn: number;
  /** Cuánto del ancho ocupa ya el que entra por la derecha; null si no se desliza. */
  push: number | null;
};

/** Cuánto se acerca el zoom de entrada en su punto más cerrado. */
export const ZOOM_DEPTH = 0.3;

const clamp01 = (p: number) => Math.min(Math.max(p, 0), 1);

/** Arranca y frena suave. */
export const smooth = (p: number): number => {
  const x = clamp01(p);
  return x * x * (3 - 2 * x);
};

const STILL: Look = { alpha: 0, gainOut: 1, gainIn: 1, zoomOut: 1, zoomIn: 1, push: null };

export function look(kind: TransitionKind, progress: number): Look {
  const p = clamp01(progress);
  switch (kind) {
    case "fundido":
      return { ...STILL, alpha: p };
    case "negro":
      // Baja a negro en la primera mitad y sube con el nuevo en la segunda.
      return p < 0.5 ? { ...STILL, gainOut: 1 - 2 * p } : { ...STILL, alpha: 1, gainIn: 2 * p - 1 };
    case "deslizar":
      return { ...STILL, alpha: 1, push: smooth(p) };
    case "zoom": {
      const e = smooth(p);
      return { ...STILL, alpha: smooth((p - 0.3) / 0.4), zoomOut: 1 + ZOOM_DEPTH * e, zoomIn: 1 + ZOOM_DEPTH * (1 - e) };
    }
    default:
      return { ...STILL, alpha: p >= 0.5 ? 1 : 0 };
  }
}
