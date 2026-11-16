"use client";

import { useMemo, useState } from "react";

export type DescriptionSlice = {
  /** El texto con que se publica el video, tal como lo deja el usuario. */
  text: string;
  setText: (text: string) => void;
  /** El modelo la está escribiendo: tarda lo que tarde, sin bloquear el resto. */
  writing: boolean;
  setWriting: (on: boolean) => void;
};

export function useDescriptionSlice(): DescriptionSlice {
  const [text, setText] = useState("");
  const [writing, setWriting] = useState(false);
  return useMemo(() => ({ text, setText, writing, setWriting }), [text, writing]);
}
