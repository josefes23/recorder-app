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
};

export const STEP_TITLES = ["Guion", "Voz", "Música", "Subtítulos", "Escenas", "Descripción"] as const;

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
    scenesStep(progress.scenes, progress.timelineIssues),
    progress.description ? ["done", "escrita"] : ["optional", "sin escribir"],
  ];
  return states.map(([state, note], i) => ({ n: i + 1, title: STEP_TITLES[i], state, note }));
}

/** Los que se pueden plegar sin esconder nada pendiente. */
export const foldable = (steps: StepInfo[]): number[] =>
  steps.filter((step) => step.state === "done").map((step) => step.n);
