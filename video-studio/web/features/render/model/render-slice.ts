"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { isRendering, isSettled, type JobStatus } from "@/domain/library";
import type { SliceDeps } from "@/features/studio/model/deps";

/** El render tarda minutos: preguntar cada segundo y pico basta y no satura. */
const POLL_MS = 1200;

export type RenderSlice = {
  previewUrl: string | null;
  job: JobStatus | null;
  rendering: boolean;
  showPreview: (frame: Blob) => void;
  /** Sigue un trabajo recién encolado hasta que termina o falla. */
  track: (id: number) => void;
};

export function useRenderSlice(
  { gateway, setError }: SliceDeps,
  onSettled: () => void,
): RenderSlice {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const previewRef = useRef<string | null>(null);

  const stop = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  }, []);

  const showPreview = useCallback((frame: Blob) => {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    const url = URL.createObjectURL(frame);
    previewRef.current = url;
    setPreviewUrl(url);
  }, []);

  const track = useCallback(
    (id: number) => {
      stop();
      setJob({ id, status: "queued", progress: 0, message: "En cola" });
      pollRef.current = setInterval(async () => {
        try {
          const status = await gateway.job(id);
          setJob(status);
          if (!isSettled(status)) return;
          stop();
          if (status.status === "error") {
            setError(status.message ?? status.error ?? "El render falló.");
          }
          onSettled();
        } catch {
          /* fallo puntual de red: se reintenta en el siguiente tick */
        }
      }, POLL_MS);
    },
    [gateway, setError, onSettled, stop],
  );

  /* Un intervalo vivo y una URL de blob sobreviven al desmontaje si no se
     limpian: el primero seguiría llamando a la API, la segunda filtra memoria. */
  useEffect(
    () => () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    },
    [],
  );

  return useMemo(
    () => ({ previewUrl, job, rendering: isRendering(job), showPreview, track }),
    [previewUrl, job, showPreview, track],
  );
}
