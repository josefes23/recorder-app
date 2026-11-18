"use client";

import { useCallback, useMemo, useState } from "react";

import { deleteVideo, listVideos } from "@/application/use-cases/manage-library";
import type { VideoItem } from "@/domain/library";
import type { SliceDeps } from "@/features/studio/model/deps";

export type LibrarySlice = {
  items: VideoItem[];
  load: () => Promise<void>;
  remove: (id: number) => Promise<void>;
  videoUrl: (id: number) => string;
  /** La portada guardada con el video, como descarga. */
  coverUrl: (id: number) => string;
  /** La misma portada en pequeño, para la cuadrícula. */
  posterUrl: (item: VideoItem) => string;
};

export function useLibrarySlice({ gateway, run }: SliceDeps): LibrarySlice {
  const [items, setItems] = useState<VideoItem[]>([]);

  const load = useCallback(async () => {
    setItems(await listVideos(gateway));
  }, [gateway]);

  const remove = useCallback(
    async (id: number) => {
      const rest = await run("library", () => deleteVideo(gateway, id));
      if (rest) setItems(rest);
    },
    [gateway, run],
  );

  const { posterUrl } = gateway;
  const poster = useCallback((item: VideoItem) => posterUrl(item.id, item.created_at), [posterUrl]);

  return useMemo(
    () => ({ items, load, remove, videoUrl: gateway.videoUrl, coverUrl: gateway.coverUrl, posterUrl: poster }),
    [items, load, remove, gateway.videoUrl, gateway.coverUrl, poster],
  );
}
