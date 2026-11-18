"use client";

import { useCallback, useMemo, useState } from "react";

export type VoiceSlice = {
  id: string;
  setId: (id: string) => void;
  /** Porcentaje sobre la velocidad natural de la voz. */
  rate: number;
  setRate: (rate: number) => void;
  /** Desplazamiento del tono en hercios. */
  pitch: number;
  setPitch: (pitch: number) => void;
  /** Voz, velocidad y tono de un video en blanco. `id`: la voz por defecto del servidor. */
  reset: (id?: string) => void;
};

/** La voz por defecto se sustituye por la primera del servidor al arrancar. */
const FALLBACK_VOICE = "es-MX-DaliaNeural";

export function useVoiceSlice(): VoiceSlice {
  const [id, setId] = useState(FALLBACK_VOICE);
  const [rate, setRate] = useState(8);
  const [pitch, setPitch] = useState(0);
  const reset = useCallback((first?: string) => {
    if (first) setId(first);
    setRate(8);
    setPitch(0);
  }, []);

  return useMemo(
    () => ({ id, setId, rate, setRate, pitch, setPitch, reset }),
    [id, rate, pitch, reset],
  );
}
