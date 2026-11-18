"use client";

import { useCallback, useMemo } from "react";

import type { Background } from "@/domain/background";
import { realStarts, sceneWords, scriptTokens, type SceneWords } from "@/domain/narration";
import { buildTimeline, type Timeline } from "@/domain/scene";
import { useCurrentTake } from "@/features/narration/model/use-take";
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

export type SceneMedia = {
  meta: Background | undefined;
  /** Miniatura: rápida, para listas y vistas previas. Null si no hay. */
  thumb: string | null;
  /** La imagen entera si es una imagen; la miniatura si es un clip. */
  full: string | null;
};

/** Dónde ver el fondo de una escena: la galería sabe su miniatura y su archivo. */
export function useSceneMedia(): (name: string | null | undefined) => SceneMedia {
  const { backgrounds } = useStudio();
  const { items, thumbUrl, fileUrl } = backgrounds;
  return useCallback(
    (name) => {
      const meta = name ? items.find((b) => b.name === name) : undefined;
      const thumb = meta?.thumb ? thumbUrl(meta.thumb) : null;
      return { meta, thumb, full: meta?.kind === "image" ? fileUrl(meta.name) : thumb };
    },
    [items, thumbUrl, fileUrl],
  );
}

export type SceneNarration = SceneWords & {
  /** Cuándo entra y hasta cuándo se ve: con la voz si hay toma, si no, estimado. */
  start: number;
  end: number;
};

export type Narration = {
  scenes: SceneNarration[];
  /** Las palabras del guion, en el orden en que las dice la voz. */
  tokens: string[];
  /** Los segundos salen de una toma de voz que vale para el guion de ahora. */
  real: boolean;
  /** Lo que dura el video: la voz si hay toma, la estimación si no. */
  total: number;
};

/**
 * Qué dice la voz mientras se ve cada escena, y cuándo. Las palabras son las
 * mismas antes y después de renderizar; los segundos, reales si hay una toma
 * de voz para el guion y la voz de ahora.
 */
export function useNarration(): Narration {
  const { scenes, script } = useStudio();
  const timeline = useTimeline();
  const { take } = useCurrentTake();
  return useMemo(() => {
    const words = sceneWords(scenes.items, script.text);
    const starts = take
      ? realStarts(scenes.items, script.text, take.words)
      : timeline.segments.map((segment) => segment.start);
    const total = take ? take.duration : timeline.total;
    const order = starts.map((_, i) => i).sort((a, b) => starts[a] - starts[b] || a - b);
    const ends: number[] = new Array(starts.length);
    order.forEach((index, position) => {
      ends[index] = position + 1 < order.length ? starts[order[position + 1]] : total;
    });
    return {
      scenes: words.map((w, i) => ({ ...w, start: starts[i], end: Math.max(starts[i], ends[i]) })),
      tokens: scriptTokens(script.text),
      real: take !== null,
      total,
    };
  }, [scenes.items, script.text, take, timeline]);
}
