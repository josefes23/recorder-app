"use client";

import { useCallback, useMemo, useState } from "react";

import type { AnimationSettings } from "@/domain/animation";
import type { SliceDeps } from "@/features/studio/model/deps";

export type AnimationSlice = {
  /** Con qué se anima y a qué precio; null hasta que contesta el servidor. */
  settings: AnimationSettings | null;
  /** Hay clave: se puede animar. */
  ready: boolean;
  /**
   * El interruptor del video: con él prendido, cada imagen nueva que llega a
   * una escena se anima sola. Apagado de serie, porque cada segundo se paga.
   */
  auto: boolean;
  setAuto: (auto: boolean) => void;
  load: () => Promise<void>;
};

export function useAnimationSlice({ gateway }: SliceDeps): AnimationSlice {
  const [settings, setSettings] = useState<AnimationSettings | null>(null);
  const [auto, setAuto] = useState(false);

  const load = useCallback(async () => {
    setSettings(await gateway.animationSettings());
  }, [gateway]);

  const ready = Boolean(settings?.ready);

  return useMemo(
    () => ({ settings, ready, auto: auto && ready, setAuto, load }),
    [settings, ready, auto, load],
  );
}
