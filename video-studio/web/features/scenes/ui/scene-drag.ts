import type { DragEvent } from "react";

/**
 * Arrastrar una escena: la lista y la barra se entienden con el mismo tipo de
 * dato, así que una imagen se puede soltar en cualquiera de las dos.
 */
export const SCENE_DRAG = "application/x-video-studio-scene";

export const carriesScene = (event: DragEvent): boolean => event.dataTransfer.types.includes(SCENE_DRAG);

export function startSceneDrag(event: DragEvent, index: number) {
  event.dataTransfer.setData(SCENE_DRAG, String(index));
  event.dataTransfer.effectAllowed = "move";
}

/** La escena que se soltó, o null si lo soltado no es una escena. */
export function droppedScene(event: DragEvent): number | null {
  const raw = event.dataTransfer.getData(SCENE_DRAG);
  const index = raw === "" ? NaN : Number(raw);
  return Number.isInteger(index) ? index : null;
}

/** Dónde cae sobre una fila: arriba o abajo inserta, en el centro intercambia. */
export type DropZone = "before" | "after" | "swap";

export function zoneOf(event: DragEvent<HTMLElement>): DropZone {
  const rect = event.currentTarget.getBoundingClientRect();
  const y = (event.clientY - rect.top) / Math.max(rect.height, 1);
  return y < 0.3 ? "before" : y > 0.7 ? "after" : "swap";
}

/** Adónde va la imagen al soltarla antes o después de la fila `index`. */
export function insertionTarget(from: number, index: number, zone: "before" | "after"): number {
  const slot = zone === "after" ? index + 1 : index;
  return from < slot ? slot - 1 : slot;
}
