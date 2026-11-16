/**
 * Guiones con diálogo: cada línea que empieza con un nombre en MAYÚSCULAS y dos
 * puntos («ANA: ¿Viste eso?») la dice ese personaje con su voz; las demás, el
 * narrador. Las mismas reglas que `app/domain/dialogue.py`.
 */
import type { Voice } from "./voice.ts";

/** «ANA:», «DON PEDRO:», «NARRADORA:». Hasta 30 caracteres: más es una frase. */
const LABEL = /^\s*([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ ]{0,29}?)\s*:\s*(.*)$/;

const NARRATOR_LABELS = new Set(["NARRADOR", "NARRADORA", "NARRACIÓN", "NARRACION", "VOZ EN OFF"]);

export const MAX_SPEAKERS = 8;

/** Voz de cada personaje: etiqueta en mayúsculas → id de la voz. */
export type DialogueVoices = Record<string, string>;

/** El guion sin las etiquetas del principio de cada línea: lo que se oye y se subtitula. */
export function withoutLabels(script: string): string {
  return script
    .split(/\r?\n/)
    .map((row) => {
      const match = LABEL.exec(row);
      return match && match[2].trim() ? match[2] : row;
    })
    .join("\n");
}

/** Las etiquetas que aparecen al principio de una línea, sin el narrador, en orden. */
export function speakersIn(script: string): string[] {
  const found: string[] = [];
  for (const row of script.split(/\r?\n/)) {
    const match = LABEL.exec(row);
    if (!match || !match[2].trim()) continue;
    const name = match[1].trim();
    if (!NARRATOR_LABELS.has(name) && !found.includes(name)) found.push(name);
  }
  return found.slice(0, MAX_SPEAKERS);
}

/**
 * Con qué voz suena mejor un nombre, a ojo: en español los terminados en «a»
 * suelen ser de mujer (ANA, LUCÍA) y el resto de hombre (PEDRO, JOSÉ). Es solo
 * el punto de partida: la voz de cada personaje se cambia a mano.
 */
export function guessVoiceGender(name: string): "♀" | "♂" {
  return /[AÁ]$/.test(name.trim().split(/\s+/)[0] ?? "") ? "♀" : "♂";
}

/**
 * Una voz para cada personaje: la que ya tenía elegida, o la siguiente libre
 * de la lista que no sea la del narrador y que encaje con su nombre (♀/♂ en la
 * etiqueta de la voz). Si no queda ninguna así, cualquier libre; con más
 * personajes que voces, se repiten.
 */
export function assignVoices(
  speakers: string[],
  voices: Voice[],
  narrator: string,
  current: DialogueVoices = {},
): DialogueVoices {
  const pool = voices.filter((v) => v.id !== narrator);
  const taken = new Set(speakers.map((s) => current[s]).filter(Boolean));
  const assigned: DialogueVoices = {};
  let next = 0;
  for (const speaker of speakers) {
    const kept = current[speaker];
    if (kept && voices.some((v) => v.id === kept)) {
      assigned[speaker] = kept;
      continue;
    }
    const gender = guessVoiceGender(speaker);
    const free = pool.filter((v) => !taken.has(v.id));
    const choice =
      free.find((v) => v.label.includes(gender)) ?? free[0] ?? pool[next++ % Math.max(pool.length, 1)];
    if (!choice) continue;
    assigned[speaker] = choice.id;
    taken.add(choice.id);
  }
  return assigned;
}
