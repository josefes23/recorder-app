"use client";

import { useCallback, useMemo, useState } from "react";

export type StatusSlice = {
  /** Clave de la acción en curso, o null. Bloquea el resto de botones. */
  busy: string | null;
  error: string | null;
  /** La clave de la acción que falló: decide dónde se enseña el error (`errorPlace`). */
  failedOn: string | null;
  /** Sin `on`, el error es general y sale en el panel de salida. */
  setError: (message: string | null, on?: string) => void;
  run: <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;
};

/**
 * Ocupado y error viven aquí porque los comparten todas las features.
 *
 * `run` concentra el ciclo que antes se repetía en cada acción: marcar
 * ocupado, limpiar el error anterior, capturar el fallo y soltar el ocupado
 * pase lo que pase. Devuelve undefined si la acción falló. El error recuerda
 * qué acción lo dio, para enseñarlo junto a su botón.
 */
export function useStatusSlice(): StatusSlice {
  const [busy, setBusy] = useState<string | null>(null);
  const [failure, setFailure] = useState<{ message: string; on: string | null } | null>(null);

  const setError = useCallback(
    (message: string | null, on?: string) => setFailure(message ? { message, on: on ?? null } : null),
    [],
  );

  const run = useCallback(async <T,>(key: string, action: () => Promise<T>) => {
    setBusy(key);
    setFailure(null);
    try {
      return await action();
    } catch (err) {
      setFailure({ message: err instanceof Error ? err.message : String(err), on: key });
      return undefined;
    } finally {
      setBusy(null);
    }
  }, []);

  return useMemo(
    () => ({ busy, error: failure?.message ?? null, failedOn: failure?.on ?? null, setError, run }),
    [busy, failure, setError, run],
  );
}
