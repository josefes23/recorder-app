"use client";

import { useMemo } from "react";

import { takeSignature, type Take, type TakeInput } from "@/domain/narration";
import { formatPitch, formatRate } from "@/domain/voice";
import { useStudio } from "@/features/studio/model/studio-context";

/** Lo que se le daría a la voz ahora mismo: lo mismo que lleva el render. */
export function useTakeInput(): TakeInput {
  const { script, voice, production } = useStudio();
  return useMemo(
    () => ({
      script: script.text,
      voice: voice.id,
      rate: formatRate(voice.rate),
      pitch: formatPitch(voice.pitch),
      voices: production.dialogue ? production.voices : {},
    }),
    [script.text, voice.id, voice.rate, voice.pitch, production.dialogue, production.voices],
  );
}

export type CurrentTake = {
  /** La toma, si vale para el guion y la voz de ahora; si no, null. */
  take: Take | null;
  /** Hay una, pero de otro guion u otra voz: hay que generarla de nuevo. */
  stale: boolean;
  generating: boolean;
  error: string | null;
  generate: () => Promise<void>;
  audioUrl: string | null;
};

export function useCurrentTake(): CurrentTake {
  const { take: slice } = useStudio();
  const input = useTakeInput();
  const signature = takeSignature(input);
  const valid = slice.take !== null && slice.signature === signature;
  return {
    take: valid ? slice.take : null,
    stale: slice.take !== null && !valid,
    generating: slice.generating,
    error: slice.error,
    generate: () => slice.generate(input),
    audioUrl: valid && slice.take?.audio ? slice.audioUrl(slice.take.key) : null,
  };
}
