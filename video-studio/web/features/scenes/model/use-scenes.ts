"use client";

import { buildTimeline, type Timeline } from "@/domain/scene";
import { useStudio } from "@/features/studio/model/studio-context";

export const useScenes = () => useStudio().scenes;

/**
 * La línea de tiempo cruza tres features: las escenas dicen dónde entra cada
 * una, el guion cuánto dura la voz, y la galería cuánto dura cada clip —que es
 * lo que decide si se repetirá—. Se calcula aquí, no en el componente.
 */
export function useTimeline(): Timeline {
  const { scenes, script, backgrounds } = useStudio();

  // Solo los vídeos se repiten: a una imagen el motor le aplica un zoom lento
  // que cubre el tramo entero.
  const clips = scenes.items.map((scene) => {
    const meta = backgrounds.items.find((b) => b.name === scene.background);
    return meta?.kind === "video" ? meta.duration : 0;
  });

  return buildTimeline(scenes.items, script.seconds, clips);
}
