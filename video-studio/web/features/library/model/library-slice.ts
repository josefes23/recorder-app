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

  return useMemo(
    () => ({ items, load, remove, videoUrl: gateway.videoUrl }),
    [items, load, remove, gateway.videoUrl],
  );
}
