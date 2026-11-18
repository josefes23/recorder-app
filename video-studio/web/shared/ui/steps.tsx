"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

/** Qué pasos están plegados. Solo es estado de la pantalla: no viaja a ningún sitio. */
export type StepsUi = {
  folded: ReadonlySet<number>;
  toggle: (n: number) => void;
  fold: (ns: number[]) => void;
  unfold: (n: number) => void;
  unfoldAll: () => void;
};

const StepsContext = createContext<StepsUi | null>(null);

export function StepsProvider({ children }: { children: ReactNode }) {
  const [folded, setFolded] = useState<ReadonlySet<number>>(() => new Set());

  const toggle = useCallback(
    (n: number) =>
      setFolded((prev) => {
        const next = new Set(prev);
        if (next.has(n)) next.delete(n);
        else next.add(n);
        return next;
      }),
    [],
  );
  const fold = useCallback((ns: number[]) => setFolded((prev) => new Set([...prev, ...ns])), []);
  const unfold = useCallback(
    (n: number) =>
      setFolded((prev) => {
        if (!prev.has(n)) return prev;
        const next = new Set(prev);
        next.delete(n);
        return next;
      }),
    [],
  );
  const unfoldAll = useCallback(() => setFolded(new Set()), []);

  const value = useMemo(() => ({ folded, toggle, fold, unfold, unfoldAll }), [folded, toggle, fold, unfold, unfoldAll]);
  return <StepsContext.Provider value={value}>{children}</StepsContext.Provider>;
}

/** Null fuera de un `StepsProvider`: el paso se queda siempre abierto. */
export const useSteps = () => useContext(StepsContext);

/** El ancla de cada paso: el índice de arriba enlaza aquí. */
export const stepAnchor = (n: number) => `paso-${n}`;
