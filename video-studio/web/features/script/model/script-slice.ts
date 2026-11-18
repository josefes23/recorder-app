"use client";

import { useCallback, useMemo, useState } from "react";

import { countWords, durationVerdict, estimateSeconds, type DurationVerdict } from "@/domain/script";

export type ScriptSlice = {
  topic: string;
  setTopic: (topic: string) => void;
  notes: string;
  setNotes: (notes: string) => void;
  text: string;
  setText: (script: string) => void;
  /** Vuelve al video en blanco: sin tema, sin indicaciones y sin guion. */
  reset: () => void;
  /* Derivados del dominio, no del componente */
  words: number;
  seconds: number;
  verdict: DurationVerdict;
};

/** `range`: la horquilla de duración del video (reel o cortometraje), para el veredicto. */
export function useScriptSlice(range?: [number, number]): ScriptSlice {
  const [topic, setTopic] = useState("");
  const [notes, setNotes] = useState("");
  const [text, setText] = useState("");
  const reset = useCallback(() => {
    setTopic("");
    setNotes("");
    setText("");
  }, []);

  return useMemo(
    () => ({
      topic, setTopic,
      notes, setNotes,
      text, setText, reset,
      words: countWords(text),
      seconds: estimateSeconds(text),
      verdict: durationVerdict(text, range),
    }),
    [topic, notes, text, range, reset],
  );
}
