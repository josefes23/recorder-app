"use client";

import { useCallback, useMemo, useState } from "react";

import { appended, without, withBackground, withStart, type Scene } from "@/domain/scene";

export type ScenesSlice = {
  items: Scene[];
  replaceAll: (scenes: Scene[]) => void;
  /** Encadena una escena nueva al final, o cambia el fondo de la que se indique. */
  place: (background: string, index: number | null) => void;
  setStart: (index: number, start: number) => void;
  remove: (index: number) => void;
};

export function useScenesSlice(): ScenesSlice {
  const [items, setItems] = useState<Scene[]>([]);

  const place = useCallback(
    (background: string, index: number | null) =>
      setItems((prev) =>
        index === null ? appended(prev, background) : withBackground(prev, index, background),
      ),
    [],
  );

  const setStart = useCallback(
    (index: number, start: number) => setItems((prev) => withStart(prev, index, start)),
    [],
  );

  const remove = useCallback((index: number) => setItems((prev) => without(prev, index)), []);

  return useMemo(
    () => ({ items, replaceAll: setItems, place, setStart, remove }),
    [items, place, setStart, remove],
  );
}
