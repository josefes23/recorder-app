"use client";

import { useCallback, useMemo, useState } from "react";

import type { PromptInfo, PromptPreview } from "@/domain/prompts";
import type { SliceDeps } from "@/features/studio/model/deps";

export type PromptsSlice = {
  items: PromptInfo[];
  /** Se carga al abrir el panel, no al arrancar: casi nadie lo usa a diario. */
  load: () => Promise<void>;
  save: (id: string, text: string) => Promise<boolean>;
  reset: (id: string) => Promise<boolean>;
  preview: (id: string, text: string) => Promise<PromptPreview | null>;
};

export function usePromptsSlice({ gateway, setError }: SliceDeps): PromptsSlice {
  const [items, setItems] = useState<PromptInfo[]>([]);

  const replace = useCallback(
    (saved: PromptInfo) => setItems((prev) => prev.map((p) => (p.id === saved.id ? saved : p))),
    [],
  );

  const load = useCallback(async () => {
    try {
      setItems(await gateway.prompts());
    } catch (error) {
      setError(error instanceof Error ? error.message : "No se pudieron cargar los prompts.");
    }
  }, [gateway, setError]);

  const save = useCallback(
    async (id: string, text: string) => {
      try {
        replace(await gateway.savePrompt(id, text));
        return true;
      } catch (error) {
        setError(error instanceof Error ? error.message : "No se pudo guardar el prompt.");
        return false;
      }
    },
    [gateway, replace, setError],
  );

  const reset = useCallback(
    async (id: string) => {
      try {
        replace(await gateway.resetPrompt(id));
        return true;
      } catch (error) {
        setError(error instanceof Error ? error.message : "No se pudo restaurar el prompt.");
        return false;
      }
    },
    [gateway, replace, setError],
  );

  const preview = useCallback(
    async (id: string, text: string) => {
      try {
        return await gateway.previewPrompt(id, text);
      } catch {
        return null;
      }
    },
    [gateway],
  );

  return useMemo(() => ({ items, load, save, reset, preview }), [items, load, save, reset, preview]);
}
