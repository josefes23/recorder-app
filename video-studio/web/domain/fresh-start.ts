/**
 * Empezar de cero borra lo que haya en el estudio. Aquí se decide cuándo hay
 * algo que perder y qué se le dice al usuario antes de hacerlo.
 */
import { sceneState, type Scene } from "./scene.ts";

export type WorkInProgress = {
  topic: string;
  script: string;
  description: string;
  scenes: Scene[];
  rendering: boolean;
};

/** Qué hay abierto que se perdería: vacío si el estudio está en blanco. */
export function whatWouldBeLost(work: WorkInProgress): string[] {
  const lost: string[] = [];
  if (work.topic.trim() || work.script.trim()) lost.push("el tema y el guion");
  if (work.scenes.length > 0) lost.push(work.scenes.length === 1 ? "la escena" : `las ${work.scenes.length} escenas`);
  if (work.description.trim()) lost.push("la descripción");
  return lost;
}

/** Avisos extra: cosas en camino que se quedarán sin dónde llegar. */
export function inFlight(work: WorkInProgress): string[] {
  const notes: string[] = [];
  const arriving = work.scenes.filter((s) => ["painting", "animating"].includes(sceneState(s))).length;
  if (arriving > 0) notes.push("Hay imágenes o clips todavía en camino: llegarán a la galería, pero no a estas escenas.");
  if (work.rendering) notes.push("Hay un render en curso: sigue su camino y lo verás en la biblioteca.");
  return notes;
}
