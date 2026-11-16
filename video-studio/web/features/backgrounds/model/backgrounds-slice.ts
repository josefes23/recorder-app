"use client";

import { useCallback, useMemo, useState } from "react";

import {
  deleteBackground,
  downloadStock,
  listBackgrounds,
  searchStock,
  uploadBackground,
} from "@/application/use-cases/manage-backgrounds";
import type { Background } from "@/domain/background";
import { markOwned, releaseOwned, type DownloadReport, type StockSearch } from "@/domain/stock";
import type { FormatId } from "@/domain/production";
import type { SliceDeps } from "@/features/studio/model/deps";

export type BackgroundsSlice = {
  items: Background[];
  /** La última búsqueda en Pexels con sus miniaturas; null hasta que se busca. */
  results: StockSearch | null;
  load: () => Promise<void>;
  search: (query: string) => Promise<void>;
  /** Baja los clips marcados de la última búsqueda; devuelve el resumen para enseñarlo. */
  download: (ids: number[]) => Promise<DownloadReport | undefined>;
  upload: (file: File) => Promise<void>;
  /** Borra un fondo de la galería; devuelve la galería al día, o undefined si falló. */
  remove: (name: string) => Promise<Background[] | undefined>;
  thumbUrl: (thumb: string | null) => string;
  /** El archivo entero del fondo, para verlo a tamaño grande. */
  fileUrl: (name: string) => string;
};

/** `format`: los clips de Pexels se buscan con la orientación del video. */
export function useBackgroundsSlice({ gateway, run }: SliceDeps, format: FormatId = "9:16"): BackgroundsSlice {
  const [items, setItems] = useState<Background[]>([]);
  const [results, setResults] = useState<StockSearch | null>(null);

  const load = useCallback(async () => {
    setItems(await listBackgrounds(gateway));
  }, [gateway]);

  const search = useCallback(
    async (query: string) => {
      const found = await run("search", () => searchStock(gateway, query, format));
      if (found) setResults(found);
    },
    [gateway, run, format],
  );

  const download = useCallback(
    async (ids: number[]) => {
      if (!results) return undefined;
      const result = await run("backgrounds", () => downloadStock(gateway, results.query, ids, format));
      if (!result) return undefined;
      setItems(result.items);
      // Los que entraron ya no se pueden volver a marcar.
      setResults((prev) => prev && { query: prev.query, clips: markOwned(prev.clips, result) });
      return result;
    },
    [gateway, run, results, format],
  );

  const upload = useCallback(
    async (file: File) => {
      const result = await run("backgrounds", () => uploadBackground(gateway, file));
      if (result) setItems(result);
    },
    [gateway, run],
  );

  const remove = useCallback(
    async (name: string) => {
      const result = await run("backgrounds", () => deleteBackground(gateway, name));
      if (!result) return undefined;
      setItems(result);
      // Si estaba entre los resultados de Pexels, vuelve a poder descargarse.
      setResults((prev) => prev && { query: prev.query, clips: releaseOwned(prev.clips, name) });
      return result;
    },
    [gateway, run],
  );

  return useMemo(
    () => ({
      items, results, load, search, download, upload, remove,
      thumbUrl: gateway.thumbUrl, fileUrl: gateway.backgroundUrl,
    }),
    [items, results, load, search, download, upload, remove, gateway.thumbUrl, gateway.backgroundUrl],
  );
}
