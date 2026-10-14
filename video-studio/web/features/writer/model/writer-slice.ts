"use client";

import { useCallback, useMemo, useState } from "react";

import { configureWriter } from "@/application/use-cases/configure-writer";
import type { Writer, WriterDraft } from "@/domain/writer";
import type { SliceDeps } from "@/features/studio/model/deps";

export type WriterSlice = {
  settings: Writer | null;
  /** Etiqueta del modelo activo, o null mientras no haya clave. */
  label: string | null;
  load: () => Promise<void>;
  save: (draft: WriterDraft) => Promise<boolean>;
};

export function useWriterSlice({ gateway, run }: SliceDeps): WriterSlice {
  const [settings, setSettings] = useState<Writer | null>(null);

  const load = useCallback(async () => {
    setSettings(await gateway.writer());
  }, [gateway]);

  const save = useCallback(
    async (draft: WriterDraft) => {
      if (!settings) return false;
      const saved = await run("writer", () => configureWriter(gateway, settings, draft));
      if (!saved) return false;
      setSettings(saved);
      return true;
    },
    [gateway, run, settings],
  );

  return useMemo(
    () => ({ settings, label: settings?.label ?? null, load, save }),
    [settings, load, save],
  );
}
