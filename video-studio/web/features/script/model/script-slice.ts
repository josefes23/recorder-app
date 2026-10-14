"use client";

import { useMemo, useState } from "react";

import { countWords, durationVerdict, estimateSeconds, type DurationVerdict } from "@/domain/script";

export type ScriptSlice = {
  topic: string;
  setTopic: (topic: string) => void;
  notes: string;
  setNotes: (notes: string) => void;
  text: string;
  setText: (script: string) => void;
  /* Derivados del dominio, no del componente */
  words: number;
  seconds: number;
  verdict: DurationVerdict;
};

export function useScriptSlice(): ScriptSlice {
  const [topic, setTopic] = useState("");
  const [notes, setNotes] = useState("");
  const [text, setText] = useState("");

  return useMemo(
    () => ({
      topic, setTopic,
      notes, setNotes,
      text, setText,
      words: countWords(text),
      seconds: estimateSeconds(text),
      verdict: durationVerdict(text),
    }),
    [topic, notes, text],
  );
}
