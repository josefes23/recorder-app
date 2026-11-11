"use client";

import { useCallback, useMemo, useState } from "react";

import type { ImageReview } from "@/domain/illustration";
import {
  appended,
  withBackground,
  withFailure,
  withImage,
  withJob,
  without,
  withStart,
  type Scene,
} from "@/domain/scene";

export type ScenesSlice = {
  items: Scene[];
  replaceAll: (scenes: Scene[]) => void;
  /** Encadena una escena nueva al final, o cambia el fondo de la que se indique. */
  place: (background: string, index: number | null) => void;
  setStart: (index: number, start: number) => void;
  remove: (index: number) => void;
  /** La escena espera una imagen pedida; `null` la añade al final. */
  startImage: (index: number | null, job: string, prompt: string) => void;
  /** Llegó la imagen de ese trabajo: la estrena la escena que la esperaba. */
  finishImage: (job: string, background: string, review?: ImageReview | null) => void;
  failImage: (job: string, error: string) => void;
};

/*
 * Las imágenes llegan cuando llegan, a veces un minuto después de pedirlas. Por
 * eso se casan con su escena por el trabajo y no por la posición —el usuario
 * puede haber borrado o reordenado entretanto—, y todo cambio va por la forma
 * funcional de `setItems`, que siempre ve el estado al día.
 */
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

  const startImage = useCallback(
    (index: number | null, job: string, prompt: string) =>
      setItems((prev) => withJob(prev, index, job, prompt)),
    [],
  );

  const finishImage = useCallback(
    (job: string, background: string, review: ImageReview | null = null) =>
      setItems((prev) => withImage(prev, job, background, review)),
    [],
  );

  const failImage = useCallback(
    (job: string, error: string) => setItems((prev) => withFailure(prev, job, error)),
    [],
  );

  return useMemo(
    () => ({
      items,
      replaceAll: setItems,
      place,
      setStart,
      remove,
      startImage,
      finishImage,
      failImage,
    }),
    [items, place, setStart, remove, startImage, finishImage, failImage],
  );
}
