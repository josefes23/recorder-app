/**
 * Qué dice la voz mientras se ve cada escena, y en qué segundo de verdad.
 *
 * El render no corta las escenas por segundos: cada una entra justo cuando la
 * voz dice una palabra concreta, la que cae en su segundo estimado al ritmo de
 * WORDS_PER_SECOND (`synced_to_voice` en `app/domain/scene.py`). Así que qué
 * palabras cubre cada imagen se sabe antes de renderizar, exacto; los segundos
 * reales salen de una toma de voz (las marcas de cada palabra). Esta es la
 * misma cuenta que la de Python: si una cambia, cambia la otra.
 */
import type { Scene } from "./scene.ts";
import { WORDS_PER_SECOND } from "./script.ts";

export type WordMark = { text: string; start: number; end: number };

/** Una toma de voz: el audio del guion y el segundo en que dice cada palabra. */
export type Take = {
  key: string;
  duration: number;
  words: WordMark[];
  /** Si el audio sigue guardado en el servidor (se guardan los últimos). */
  audio: boolean;
};

/** Lo que se le da a la voz: lo mismo que lleva el render. */
export type TakeInput = {
  script: string;
  voice: string;
  rate: string;
  pitch: string;
  /** Voz de cada personaje; vacío si no es un diálogo. */
  voices: Record<string, string>;
};

/** Con qué se generó una toma: si cambia algo, la toma ya no vale para lo de ahora. */
export const takeSignature = (input: TakeInput): string =>
  JSON.stringify([input.script, input.voice, input.rate, input.pitch, Object.entries(input.voices).sort()]);

/** `clean_script` de Python: fuera las marcas de markdown, un espacio entre palabras. */
export const cleanScript = (raw: string): string => raw.replace(/[*_#`[\]]/g, " ").replace(/\s+/g, " ").trim();

export const scriptTokens = (raw: string): string[] => {
  const clean = cleanScript(raw);
  return clean ? clean.split(" ") : [];
};

/** El `round` de Python: los empates van al par. Con el de JS, 40,5 daría otra palabra. */
export function roundHalfEven(x: number): number {
  const floor = Math.floor(x);
  const rest = x - floor;
  if (rest > 0.5) return floor + 1;
  if (rest < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

/** La palabra con que entra una escena que empieza en `start` (segundos estimados). */
export const wordAt = (start: number): number => roundHalfEven(start * WORDS_PER_SECOND);

/** El segundo estimado que hace entrar una escena justo con la palabra `k`. */
export const startForWord = (k: number): number => Math.round((k / WORDS_PER_SECOND) * 100) / 100;

export type SceneWords = {
  /** Primera palabra que se oye con esta escena (índice en el guion). */
  from: number;
  /** La primera que ya no: la de la escena siguiente. */
  to: number;
  text: string;
};

/**
 * Lo que dice la voz mientras se ve cada escena, en el orden de `scenes`. Las
 * escenas se ordenan por su palabra, como en el render; la primera arranca
 * siempre en la primera palabra. Una que entra después de la voz no dice nada.
 */
export function sceneWords(scenes: Scene[], script: string): SceneWords[] {
  const tokens = scriptTokens(script);
  const ks = scenes.map((scene, i) => (i === 0 ? 0 : Math.min(wordAt(scene.start), tokens.length)));
  const order = ks.map((_, i) => i).sort((a, b) => ks[a] - ks[b] || a - b);
  const result: SceneWords[] = new Array(scenes.length);
  order.forEach((index, position) => {
    const from = ks[index];
    const to = position + 1 < order.length ? ks[order[position + 1]] : tokens.length;
    result[index] = { from, to: Math.max(from, to), text: tokens.slice(from, Math.max(from, to)).join(" ") };
  });
  return result;
}

// --------------------------------------------------------------------------- //
// Del segundo estimado al de la voz: `synced_to_voice`, copiado
// --------------------------------------------------------------------------- //

/** Cuántas palabras del guion puede saltarse la voz sin perder el hilo. */
const ALIGN_WINDOW = 6;

const norm = (text: string): string => text.replace(/[^\p{L}\p{N}_]/gu, "").toLowerCase();

type Mark = [number, number] | null;

function voiceMarks(tokens: string[], words: WordMark[]): Mark[] {
  const keys = tokens.map(norm);
  const marks: Mark[] = new Array(tokens.length).fill(null);
  let ti = 0;
  for (const word of words) {
    const target = norm(word.text);
    if (!target) continue;
    let j = ti;
    const limit = Math.min(keys.length, ti + ALIGN_WINDOW);
    while (j < limit && keys[j] !== target) j++;
    if (j < limit) {
      marks[j] = [word.start, word.end];
      ti = j + 1;
    }
  }
  return marks;
}

function cutBefore(k: number, marks: Mark[]): number | null {
  let after: number | null = null;
  for (let j = k; j < marks.length; j++) if (marks[j]) { after = j; break; }
  let before: number | null = null;
  for (let i = k - 1; i >= 0; i--) if (marks[i]) { before = i; break; }
  if (after === k && before === k - 1) return (marks[before]![1] + marks[after]![0]) / 2;
  if (after === k) return marks[after]![0];
  if (before !== null) return marks[before]![1];
  return after === null ? null : marks[after]![0];
}

/**
 * El segundo en que entra cada escena con esa toma: el mismo que usará el
 * render. Sin marcas, los segundos estimados.
 */
export function realStarts(scenes: Scene[], script: string, words: WordMark[]): number[] {
  const tokens = scriptTokens(script);
  const marks = voiceMarks(tokens, words);
  const known = marks.filter((m): m is [number, number] => m !== null);
  if (known.length === 0) return scenes.map((scene, i) => (i === 0 ? 0 : scene.start));
  const voiceEnd = known[known.length - 1][1];
  const estimatedEnd = tokens.length / WORDS_PER_SECOND;
  return scenes.map((scene, i) => {
    if (i === 0) return 0;
    const k = wordAt(scene.start);
    if (k <= 0) return scene.start;
    if (k >= tokens.length) return Math.round((voiceEnd + scene.start - estimatedEnd) * 100) / 100;
    const cut = cutBefore(k, marks);
    return cut === null ? scene.start : Math.round(cut * 100) / 100;
  });
}

/** Cuántas palabras enseña a la vez el subtítulo de la animática con voz. */
const CAPTION_WORDS = 6;

/**
 * Lo que está diciendo la voz en el segundo `t`, en bloques como los
 * subtítulos. Vacío antes de la primera palabra y un poco después de la última.
 */
export function spokenAt(words: WordMark[], t: number, block = CAPTION_WORDS): string {
  let low = 0;
  let high = words.length - 1;
  let at = -1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (words[mid].start <= t) {
      at = mid;
      low = mid + 1;
    } else high = mid - 1;
  }
  if (at < 0 || (at === words.length - 1 && t > words[at].end + 1)) return "";
  const from = Math.floor(at / block) * block;
  return words
    .slice(from, from + block)
    .map((word) => word.text)
    .join(" ");
}

/**
 * Entre qué palabras puede empezar la escena `index` sin pisar a sus vecinas:
 * después de la palabra con que entra la anterior y antes de la de la
 * siguiente, y siempre diciendo algo. Null para la primera, que empieza con la
 * primera palabra.
 */
export function movableWords(words: SceneWords[], index: number, tokenCount: number): [number, number] | null {
  if (index <= 0 || index >= words.length || tokenCount === 0) return null;
  const from = words[index].from;
  let previous = 0;
  let next = tokenCount;
  words.forEach((other, i) => {
    if (i === index) return;
    if (other.from < from || (other.from === from && i < index)) previous = Math.max(previous, other.from);
    else next = Math.min(next, other.from);
  });
  const low = previous + 1;
  const high = Math.min(next - 1, tokenCount - 1);
  return low <= high ? [low, high] : null;
}
