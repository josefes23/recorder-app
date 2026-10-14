/** Ritmo medido con las voces es-* a +8 %: 2,7 palabras por segundo. */
export const WORDS_PER_SECOND = 2.7;

/** Fuera de esta horquilla el Reel se hace corto o se hace pesado. */
export const MIN_SECONDS = 28;
export const MAX_SECONDS = 48;

export type DurationVerdict = "empty" | "short" | "ok" | "long";

export function countWords(script: string): number {
  const trimmed = script.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

export function estimateSeconds(script: string): number {
  return countWords(script) / WORDS_PER_SECOND;
}

/**
 * Verdicto, no mensaje: el dominio decide si la duración sirve y la interfaz
 * decide cómo decirlo.
 */
export function durationVerdict(script: string): DurationVerdict {
  const words = countWords(script);
  if (words === 0) return "empty";
  const seconds = words / WORDS_PER_SECOND;
  if (seconds < MIN_SECONDS) return "short";
  if (seconds > MAX_SECONDS) return "long";
  return "ok";
}

export const canRender = (script: string): boolean => countWords(script) > 0;

/**
 * Muestra para el fotograma de previsualización: las primeras palabras del
 * guion, que es lo que se verá en el primer bloque de subtítulo.
 */
export function sampleCaption(script: string, words = 5): string {
  const sample = script.trim().split(/\s+/).filter(Boolean).slice(0, words).join(" ");
  return sample || "Texto de ejemplo";
}
