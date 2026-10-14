"use client";

import { useCallback, useMemo, useState } from "react";

import { DEFAULT_STYLE, type Style } from "@/domain/captions";

export type CaptionsSlice = {
  style: Style;
  setField: <K extends keyof Style>(key: K, value: Style[K]) => void;
  /** Aplica un estilo entero: el del servidor al arrancar, o el de un video reutilizado. */
  apply: (style: Partial<Style>) => void;
};

export function useCaptionsSlice(): CaptionsSlice {
  const [style, setStyle] = useState<Style>(DEFAULT_STYLE);

  const setField = useCallback(
    <K extends keyof Style>(key: K, value: Style[K]) =>
      setStyle((prev) => ({ ...prev, [key]: value })),
    [],
  );

  const apply = useCallback(
    (partial: Partial<Style>) => setStyle((prev) => ({ ...prev, ...partial })),
    [],
  );

  return useMemo(() => ({ style, setField, apply }), [style, setField, apply]);
}
