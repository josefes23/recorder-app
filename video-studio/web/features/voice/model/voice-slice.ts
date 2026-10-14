"use client";

import { useMemo, useState } from "react";

export type VoiceSlice = {
  id: string;
  setId: (id: string) => void;
  /** Porcentaje sobre la velocidad natural de la voz. */
  rate: number;
  setRate: (rate: number) => void;
  /** Desplazamiento del tono en hercios. */
  pitch: number;
  setPitch: (pitch: number) => void;
};

/** La voz por defecto se sustituye por la primera del servidor al arrancar. */
const FALLBACK_VOICE = "es-MX-DaliaNeural";

export function useVoiceSlice(): VoiceSlice {
  const [id, setId] = useState(FALLBACK_VOICE);
  const [rate, setRate] = useState(8);
  const [pitch, setPitch] = useState(0);

  return useMemo(
    () => ({ id, setId, rate, setRate, pitch, setPitch }),
    [id, rate, pitch],
  );
}
