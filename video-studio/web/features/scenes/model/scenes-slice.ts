"use client";

import { useCallback, useMemo, useState } from "react";

import type { ImageReview } from "@/domain/illustration";
import {
  appended,
  withBackground,
  withClip,
  withClipFailure,
  withClipFailureOn,
  withClipJobAt,
  withClipJobOn,
  withFailure,
  withImage,
  withJob,
  without,
  withStart,
  withStillImage,
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
  /** La escena espera un clip animado: por posición (botón) o por su imagen (animación automática). */
  startClipAt: (index: number, job: string) => void;
  startClipOn: (background: string, job: string) => void;
  /** Llegó el clip: la escena que lo esperaba lo estrena y guarda su imagen. */
  finishClip: (job: string, clip: string) => void;
  failClip: (job: string, error: string) => void;
  failClipOn: (background: string, error: string) => void;
  /** Vuelve a la imagen fija de la que salió el clip. */
  restoreStill: (index: number) => void;
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

  const startClipAt = useCallback(
    (index: number, job: string) => setItems((prev) => withClipJobAt(prev, index, job)),
    [],
  );
  const startClipOn = useCallback(
    (background: string, job: string) => setItems((prev) => withClipJobOn(prev, background, job)),
    [],
  );
  const finishClip = useCallback(
    (job: string, clip: string) => setItems((prev) => withClip(prev, job, clip)),
    [],
  );
  const failClip = useCallback(
    (job: string, error: string) => setItems((prev) => withClipFailure(prev, job, error)),
    [],
  );
  const failClipOn = useCallback(
    (background: string, error: string) => setItems((prev) => withClipFailureOn(prev, background, error)),
    [],
  );
  const restoreStill = useCallback(
    (index: number) => setItems((prev) => withStillImage(prev, index)),
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
      startClipAt,
      startClipOn,
      finishClip,
      failClip,
      failClipOn,
      restoreStill,
    }),
    [
      items, place, setStart, remove, startImage, finishImage, failImage,
      startClipAt, startClipOn, finishClip, failClip, failClipOn, restoreStill,
    ],
  );
}
