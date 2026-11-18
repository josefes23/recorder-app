"use client";

import { useCallback, useMemo, useState } from "react";

import type { GrowthKind, GrowthResults } from "@/domain/growth";

export type GrowthSlice = {
  /** Lo último que dijo el modelo de cada consejo. */
  results: { [K in GrowthKind]?: GrowthResults[K] };
  /** Los consejos que se están pidiendo: tardan lo que tarde el modelo. */
  pending: ReadonlySet<GrowthKind>;
  setResult: <K extends GrowthKind>(kind: K, result: GrowthResults[K]) => void;
  setPending: (kind: GrowthKind, on: boolean) => void;
  /** El último gancho puesto en el guion: para cambiarlo sin apilar dos. */
  appliedHook: string | null;
  setAppliedHook: (hook: string | null) => void;
};

export function useGrowthSlice(): GrowthSlice {
  const [results, setResults] = useState<GrowthSlice["results"]>({});
  const [pending, setPendingSet] = useState<ReadonlySet<GrowthKind>>(new Set());
  const [appliedHook, setAppliedHook] = useState<string | null>(null);

  const setResult = useCallback(
    <K extends GrowthKind>(kind: K, result: GrowthResults[K]) => setResults((prev) => ({ ...prev, [kind]: result })),
    [],
  );
  const setPending = useCallback(
    (kind: GrowthKind, on: boolean) =>
      setPendingSet((prev) => {
        const next = new Set(prev);
        if (on) next.add(kind);
        else next.delete(kind);
        return next;
      }),
    [],
  );

  return useMemo(
    () => ({ results, pending, setResult, setPending, appliedHook, setAppliedHook }),
    [results, pending, setResult, setPending, appliedHook],
  );
}
