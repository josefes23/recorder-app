"use client";

import { useCallback, useMemo, useState } from "react";

import type { SavedCharacter } from "@/domain/illustration";
import type { SliceDeps } from "@/features/studio/model/deps";

export type CharactersSlice = {
  /** La biblioteca de elementos que se repiten entre videos, lo último primero. */
  items: SavedCharacter[];
  /** Ids cuya imagen de referencia se está pintando ahora. */
  painting: number[];
  /** Por qué falló la última imagen de referencia de cada uno. */
  failures: Record<number, string>;
  load: () => Promise<void>;
  remove: (id: number) => Promise<boolean>;
  setPainting: (id: number, painting: boolean) => void;
  setFailure: (id: number, detail: string | null) => void;
  /** Su imagen de referencia, o null si aún no la tiene. */
  referenceUrl: (saved: SavedCharacter) => string | null;
};

export function useCharactersSlice({ gateway, run }: SliceDeps): CharactersSlice {
  const [items, setItems] = useState<SavedCharacter[]>([]);
  const [painting, setPaintingIds] = useState<number[]>([]);
  const [failures, setFailures] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    setItems(await gateway.characters());
  }, [gateway]);

  const remove = useCallback(
    async (id: number) => {
      const done = await run(`character-${id}`, () => gateway.deleteCharacter(id).then(() => true));
      if (!done) return false;
      setItems((prev) => prev.filter((c) => c.id !== id));
      return true;
    },
    [gateway, run],
  );

  const setPainting = useCallback((id: number, on: boolean) => {
    setPaintingIds((prev) => (on ? [...new Set([...prev, id])] : prev.filter((p) => p !== id)));
  }, []);

  const setFailure = useCallback((id: number, detail: string | null) => {
    setFailures((prev) => {
      const next = { ...prev };
      if (detail) next[id] = detail;
      else delete next[id];
      return next;
    });
  }, []);

  const referenceUrl = useCallback(
    (saved: SavedCharacter) => (saved.reference ? gateway.referenceUrl(saved.reference, saved.updated_at) : null),
    [gateway],
  );

  return useMemo(
    () => ({ items, painting, failures, load, remove, setPainting, setFailure, referenceUrl }),
    [items, painting, failures, load, remove, setPainting, setFailure, referenceUrl],
  );
}
