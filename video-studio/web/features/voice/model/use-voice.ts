"use client";

import { useStudio } from "@/features/studio/model/studio-context";

export const useVoice = () => useStudio().voice;

/** Las voces disponibles las dicta el servidor, no la feature. */
export const useVoiceCatalog = () => useStudio().config?.voices ?? [];
