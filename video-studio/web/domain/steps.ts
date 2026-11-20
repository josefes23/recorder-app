/**
 * En qué punto está cada paso del estudio, para el índice de arriba: qué está
 * listo, qué pide atención y qué falta. El dominio decide el estado; la
 * interfaz, cómo se pinta.
 */
import { sceneState, type Scene } from "./scene.ts";
import type { DurationVerdict } from "./script.ts";

/**
 * - done: listo; se puede plegar sin perder nada.
 * - warn: hay algo que revisar antes de renderizar.
 * - busy: esperando algo que llega solo (imágenes, clips).
 * - todo: falta y hace falta.
 * - optional: vacío, pero el video sale igual.
 */
export type StepState = "done" | "warn" | "busy" | "todo" | "optional";

export type StepInfo = { n: number; title: string; state: StepState; note: string };

export type StudioProgress = {
  verdict: DurationVerdict;
  music: boolean;
  scenes: Scene[];
  /** Escenas que entran después de la voz o segundos desordenados. */
  timelineIssues: boolean;
  description: boolean;
  /** El puntaje del video, si ya se pidió. */
  score: number | null;
  /** Qué retoques hay puestos en el acabado («audio», «color»…); vacío si ninguno. */
  finish: string[];
};

/**
 * El orden de los pasos. Escenas va al final a propósito: pintar las imágenes
 * cuesta tiempo y dinero, y se hace una vez que el guion, la voz y los consejos
 * de Optimizar ya están decididos. Si un consejo cambia el guion después de
 * pintar, hay que rehacer las imágenes.
 */
export const STEP = { script: 1, voice: 2, sound: 3, captions: 4, description: 5, growth: 6, scenes: 7, finish: 8 } as const;

export const STEP_TITLES = ["Guion", "Voz", "Música", "Subtítulos", "Descripción", "Optimizar", "Escenas", "Acabado"] as const;

function scenesStep(scenes: Scene[], timelineIssues: boolean): [StepState, string] {
  if (scenes.length === 0) return ["optional", "fondo generado"];
  const states = scenes.map(sceneState);
  if (states.some((s) => s === "painting" || s === "animating")) return ["busy", "llegando imágenes"];
  const failed = states.filter((s) => s === "failed" || s === "review").length;
  if (failed) return ["warn", failed === 1 ? "1 escena por revisar" : `${failed} escenas por revisar`];
  if (timelineIssues) return ["warn", "revisar los tiempos"];
  if (states.some((s) => s === "empty")) return ["warn", "escenas sin imagen"];
  return ["done", `${scenes.length} escenas`];
}

export function stepStates(progress: StudioProgress): StepInfo[] {
  const script: [StepState, string] =
    progress.verdict === "empty"
      ? ["todo", "falta el guion"]
      : progress.verdict === "ok"
        ? ["done", "duración justa"]
        : ["warn", progress.verdict === "short" ? "se queda corto" : "se pasa de largo"];
  const states: [StepState, string][] = [
    script,
    ["done", ""],
    progress.music ? ["done", "con música"] : ["optional", "solo la voz"],
    ["done", ""],
    progress.description ? ["done", "escrita"] : ["optional", "sin escribir"],
    progress.score === null ? ["optional", "ganchos, títulos y puntaje"] : ["done", `puntaje ${progress.score}`],
    scenesStep(progress.scenes, progress.timelineIssues),
    progress.finish.length ? ["done", progress.finish.join(" · ")] : ["optional", "sin retoques"],
  ];
  return states.map(([state, note], i) => ({ n: i + 1, title: STEP_TITLES[i], state, note }));
}

export type NextStep = {
  n: number;
  title: string;
  /** fix: algo falta o está por revisar; wait: llega solo; suggest: opcional pero conviene; render: no queda nada. */
  kind: "fix" | "wait" | "suggest" | "render";
  /** Lo que se le dice al usuario, en una frase. */
  message: string;
};

/**
 * Qué toca ahora. Primero el guion (todo depende de él); con el guion listo,
 * Optimizar antes de pintar nada, porque cambiarlo después obliga a rehacer la
 * voz y las imágenes; luego lo que falte o esté por revisar; al final, renderizar.
 */
export function nextStep(steps: StepInfo[]): NextStep {
  const script = steps[STEP.script - 1];
  const growth = steps[STEP.growth - 1];
  if (script.state === "todo" || script.state === "warn") {
    return { n: script.n, title: script.title, kind: "fix", message: script.state === "todo" ? "Falta escribir el guion." : `Revisa el guion: ${script.note} para la duración elegida.` };
  }
  if (growth.state === "optional") {
    return {
      n: growth.n,
      title: growth.title,
      kind: "suggest",
      message: "Sugerido: puntúa y corrige el guion en Optimizar antes de pintar escenas.",
    };
  }
  const pending = steps.find((step) => step.state === "todo" || step.state === "warn");
  if (pending) {
    return { n: pending.n, title: pending.title, kind: "fix", message: `Por revisar: ${pending.title}${pending.note ? ` (${pending.note})` : ""}.` };
  }
  const busy = steps.find((step) => step.state === "busy");
  if (busy) return { n: busy.n, title: busy.title, kind: "wait", message: `Esperando: ${busy.title} (${busy.note}).` };
  return { n: STEP.finish, title: steps[STEP.finish - 1].title, kind: "render", message: "Todo listo: puedes renderizar." };
}

/** Los que se pueden plegar sin esconder nada pendiente. */
export const foldable = (steps: StepInfo[]): number[] =>
  steps.filter((step) => step.state === "done").map((step) => step.n);
