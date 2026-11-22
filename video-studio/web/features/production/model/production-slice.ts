"use client";

import { useCallback, useMemo, useState } from "react";

import type { DialogueVoices } from "@/domain/dialogue";
import { DEFAULT_PRODUCTION, type FormatId, type LengthId, type Production } from "@/domain/production";
import type { Transition } from "@/domain/transition";

export type ProductionSlice = Production & {
  setFormat: (format: FormatId) => void;
  setLength: (length: LengthId) => void;
  setDialogue: (dialogue: boolean) => void;
  /** La voz de un personaje del diálogo. */
  setVoice: (speaker: string, voice: string) => void;
  /** Todas a la vez: al detectar personajes nuevos en el guion. */
  setVoices: (voices: DialogueVoices) => void;
  setMusic: (music: string) => void;
  setMusicVolume: (volume: number) => void;
  setAmbient: (ambient: boolean) => void;
  /** La de las escenas que no eligen la suya. */
  setTransition: (transition: Transition) => void;
  /** Lo que se guardó con un video, al reutilizarlo. */
  restore: (production: Production) => void;
};

export function useProductionSlice(): ProductionSlice {
  const [production, setProduction] = useState<Production>(DEFAULT_PRODUCTION);

  const patch = useCallback(
    (changes: Partial<Production>) => setProduction((prev) => ({ ...prev, ...changes })),
    [],
  );

  const setVoice = useCallback(
    (speaker: string, voice: string) =>
      setProduction((prev) => ({ ...prev, voices: { ...prev.voices, [speaker]: voice } })),
    [],
  );

  return useMemo(
    () => ({
      ...production,
      setFormat: (format: FormatId) => patch({ format }),
      setLength: (length: LengthId) => patch({ length }),
      setDialogue: (dialogue: boolean) => patch({ dialogue }),
      setVoice,
      setVoices: (voices: DialogueVoices) => patch({ voices }),
      setMusic: (music: string) => patch({ music }),
      setMusicVolume: (musicVolume: number) => patch({ musicVolume }),
      setAmbient: (ambient: boolean) => patch({ ambient }),
      setTransition: (transition: Transition) => patch({ transition }),
      restore: setProduction,
    }),
    [production, patch, setVoice],
  );
}
