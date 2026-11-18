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
export function durationVerdict(
  script: string,
  [min, max]: [number, number] = [MIN_SECONDS, MAX_SECONDS],
): DurationVerdict {
  const words = countWords(script);
  if (words === 0) return "empty";
  const seconds = words / WORDS_PER_SECOND;
  if (seconds < min) return "short";
  if (seconds > max) return "long";
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

/** Cuántas palabras enseña la animática a la vez: un bloque de subtítulo. */
export const ANIMATIC_WORDS = 6;

/**
 * Lo que la voz estaría diciendo en el segundo `t`, al ritmo estimado, en
 * bloques como los de los subtítulos. Vacío si la voz ya acabó. Sirve para
 * ver con qué frase cae cada imagen antes de renderizar.
 */
export function wordsAt(script: string, t: number, block = ANIMATIC_WORDS): string {
  const words = script.replaceAll("*", "").trim().split(/\s+/).filter(Boolean);
  const at = Math.floor(Math.max(t, 0) * WORDS_PER_SECOND);
  if (at >= words.length) return "";
  const from = Math.floor(at / block) * block;
  return words.slice(from, from + block).join(" ");
}
