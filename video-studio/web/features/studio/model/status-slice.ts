"use client";

import { useCallback, useMemo, useState } from "react";

export type StatusSlice = {
  /** Clave de la acción en curso, o null. Bloquea el resto de botones. */
  busy: string | null;
  error: string | null;
  setError: (message: string | null) => void;
  run: <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;
};

/**
 * Ocupado y error viven aquí porque los comparten todas las features.
 *
 * `run` concentra el ciclo que antes se repetía en cada acción: marcar
 * ocupado, limpiar el error anterior, capturar el fallo y soltar el ocupado
 * pase lo que pase. Devuelve undefined si la acción falló.
 */
export function useStatusSlice(): StatusSlice {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async <T,>(key: string, action: () => Promise<T>) => {
    setBusy(key);
    setError(null);
    try {
      return await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return undefined;
    } finally {
      setBusy(null);
    }
  }, []);

  return useMemo(() => ({ busy, error, setError, run }), [busy, error, run]);
}
