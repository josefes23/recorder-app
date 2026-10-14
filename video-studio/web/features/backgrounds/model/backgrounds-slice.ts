"use client";

import { useCallback, useMemo, useState } from "react";

import {
  downloadBackgrounds,
  listBackgrounds,
  uploadBackground,
} from "@/application/use-cases/manage-backgrounds";
import type { Background } from "@/domain/background";
import type { SliceDeps } from "@/features/studio/model/deps";

export type BackgroundsSlice = {
  items: Background[];
  load: () => Promise<void>;
  /** Descarga de Pexels; devuelve el registro del proceso para enseñarlo. */
  download: (query: string) => Promise<string | undefined>;
  upload: (file: File) => Promise<void>;
  thumbUrl: (thumb: string | null) => string;
};

export function useBackgroundsSlice({ gateway, run }: SliceDeps): BackgroundsSlice {
  const [items, setItems] = useState<Background[]>([]);

  const load = useCallback(async () => {
    setItems(await listBackgrounds(gateway));
  }, [gateway]);

  const download = useCallback(
    async (query: string) => {
      const result = await run("backgrounds", () => downloadBackgrounds(gateway, query));
      if (!result) return undefined;
      setItems(result.items);
      return result.log;
    },
    [gateway, run],
  );

  const upload = useCallback(
    async (file: File) => {
      const result = await run("backgrounds", () => uploadBackground(gateway, file));
      if (result) setItems(result);
    },
    [gateway, run],
  );

  return useMemo(
    () => ({ items, load, download, upload, thumbUrl: gateway.thumbUrl }),
    [items, load, download, upload, gateway.thumbUrl],
  );
}
