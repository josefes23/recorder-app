"use client";

import { useCallback } from "react";

import type { VideoItem } from "@/domain/library";
import { inFlight, whatWouldBeLost, type WorkInProgress } from "@/domain/fresh-start";
import { useConfirm } from "@/shared/ui/confirm";

import { useStudio } from "./studio-context";

/**
 * Empezar un video nuevo, o cargar uno de la biblioteca, borra lo que haya en
 * pantalla. Si hay algo que perder pregunta antes; si el estudio está en
 * blanco, no molesta. Devuelve si se llegó a hacer.
 */
export function useFreshStart() {
  const confirm = useConfirm();
  const { script, scenes, description, render, actions } = useStudio();

  const guard = useCallback(
    async (title: string, message: string, confirmLabel: string): Promise<boolean> => {
      const work: WorkInProgress = {
        topic: script.topic,
        script: script.text,
        description: description.text,
        scenes: scenes.items,
        rendering: render.rendering,
      };
      const lost = whatWouldBeLost(work);
      if (lost.length === 0) return true;
      return confirm({
        title,
        message: `${message} Se borrará lo que hay ahora: ${lost.join(", ")}.`,
        details: inFlight(work),
        confirmLabel,
      });
    },
    [confirm, script.topic, script.text, description.text, scenes.items, render.rendering],
  );

  const startOver = useCallback(async () => {
    if (!(await guard("¿Empezar un video nuevo?", "Todos los pasos vuelven a estar en blanco.", "Empezar de nuevo"))) return false;
    actions.startOver();
    window.scrollTo({ top: 0, behavior: "smooth" });
    return true;
  }, [guard, actions]);

  const reuse = useCallback(
    async (item: VideoItem) => {
      if (!(await guard("¿Cargar este video?", "Su guion, voz, escenas y ajustes sustituyen a los de ahora.", "Cargar y sustituir"))) return false;
      actions.reuse(item);
      return true;
    },
    [guard, actions],
  );

  return { startOver, reuse };
}
