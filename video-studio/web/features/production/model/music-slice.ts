"use client";

import { useCallback, useMemo, useState } from "react";

import type { Track } from "@/domain/music";
import type { SliceDeps } from "@/features/studio/model/deps";

export type MusicSlice = {
  tracks: Track[];
  load: () => Promise<void>;
  /** Sube una pista; devuelve su nombre en la galería, o null si falló. */
  upload: (file: File) => Promise<string | null>;
  /** La borra de la galería; true si se pudo. */
  remove: (name: string) => Promise<boolean>;
  url: (name: string) => string;
};

export function useMusicSlice({ gateway, run }: SliceDeps): MusicSlice {
  const [tracks, setTracks] = useState<Track[]>([]);

  const load = useCallback(async () => {
    setTracks(await gateway.music());
  }, [gateway]);

  const upload = useCallback(
    async (file: File) => {
      const items = await run("music", () => gateway.uploadMusic(file));
      if (!items) return null;
      setTracks(items);
      return file.name;
    },
    [gateway, run],
  );

  const remove = useCallback(
    async (name: string) => {
      const items = await run("music", () => gateway.deleteMusic(name));
      if (!items) return false;
      setTracks(items);
      return true;
    },
    [gateway, run],
  );

  return useMemo(
    () => ({ tracks, load, upload, remove, url: gateway.musicUrl }),
    [tracks, load, upload, remove, gateway],
  );
}
