"use client";

import { STEP } from "@/domain/steps";
import { useCallback } from "react";

import type { GrowthKind } from "@/domain/growth";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";
import { useSteps } from "@/shared/ui/steps";

/** El paso «Optimizar», donde se leen todos los consejos. */
export const GROWTH_STEP = STEP.growth;

/**
 * Pide un consejo desde otro paso (un atajo) y, cuando llega, lleva allí a
 * donde se lee: abre el paso de Optimizar y se desplaza a su tarjeta.
 */
export function useAdvice(): (kind: GrowthKind) => Promise<void> {
  const actions = useStudioActions();
  const steps = useSteps();
  return useCallback(
    async (kind) => {
      steps?.unfold(GROWTH_STEP);
      const ok = await actions.advise(kind);
      if (ok) document.getElementById(`growth-${kind}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    [actions, steps],
  );
}
