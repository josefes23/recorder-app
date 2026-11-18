"use client";

import { useCallback, useMemo, useRef, useState } from "react";

import { takeSignature, type Take, type TakeInput } from "@/domain/narration";
import type { SliceDeps } from "@/features/studio/model/deps";

export type TakeSlice = {
  take: Take | null;
  /** Con qué guion y voz se hizo (`takeSignature`): si ya no coincide, la toma no vale. */
  signature: string | null;
  generating: boolean;
  error: string | null;
  /** Genera la voz de eso (o trae la ya hecha). */
  generate: (input: TakeInput) => Promise<void>;
  /** La toma con que se renderizó un video, al reutilizarlo: sus tiempos reales. */
  restore: (key: string, input: TakeInput) => Promise<void>;
  clear: () => void;
  /** Dónde escuchar el audio de una toma. */
  audioUrl: (key: string) => string;
};

/*
 * La toma no pasa por `run`: generar la voz tarda unos segundos y no debe
 * bloquear el resto de botones. Lleva su propio «trabajando» y su error, que
 * se enseñan donde se pidió (la animática).
 */
export function useTakeSlice({ gateway }: Pick<SliceDeps, "gateway">): TakeSlice {
  const [take, setTake] = useState<Take | null>(null);
  const [signature, setSignature] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** Si llegan dos respuestas, vale la del último encargo. */
  const ticket = useRef(0);

  const load = useCallback(
    async (input: TakeInput, fetchTake: () => Promise<Take>) => {
      const mine = ++ticket.current;
      setGenerating(true);
      setError(null);
      try {
        const found = await fetchTake();
        if (mine !== ticket.current) return;
        setTake(found);
        setSignature(takeSignature(input));
      } catch (err) {
        if (mine === ticket.current) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (mine === ticket.current) setGenerating(false);
      }
    },
    [],
  );

  const generate = useCallback(
    (input: TakeInput) => load(input, () => gateway.requestTake(input)),
    [gateway, load],
  );
  const restore = useCallback(
    (key: string, input: TakeInput) => load(input, () => gateway.take(key)),
    [gateway, load],
  );
  const clear = useCallback(() => {
    ticket.current++;
    setTake(null);
    setSignature(null);
    setError(null);
    setGenerating(false);
  }, []);

  const { takeAudioUrl } = gateway;
  return useMemo(
    () => ({ take, signature, generating, error, generate, restore, clear, audioUrl: takeAudioUrl }),
    [take, signature, generating, error, generate, restore, clear, takeAudioUrl],
  );
}
