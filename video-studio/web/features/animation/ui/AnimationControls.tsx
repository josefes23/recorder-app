"use client";

import { estimateCost, formatUsd } from "@/domain/animation";
import { animatable } from "@/domain/scene";
import { useAnimation } from "@/features/animation/model/use-animation";
import { useScenes, useTimeline } from "@/features/scenes/model/use-scenes";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";

/**
 * El interruptor del video y «animar todas». Enseña el precio orientativo:
 * cada segundo animado se paga y no hay nivel gratuito.
 */
export function AnimationControls() {
  const animation = useAnimation();
  const scenes = useScenes();
  const timeline = useTimeline();
  const actions = useStudioActions();
  const { settings } = animation;
  if (!settings) return null;

  if (!settings.ready) {
    return (
      <p className="hint">
        Para animar las escenas con {settings.name} hace falta la clave de Google ({settings.key}) con
        la facturación activada: no tiene nivel gratuito. Ponla en «Generador de imágenes» → Google.
      </p>
    );
  }

  // Las que todavía no tienen clip: lo que haría «Animar todas».
  const pending = scenes.items.flatMap((scene, i) =>
    animatable(scene) && !scene.still ? [timeline.segments[i]?.span ?? 0] : [],
  );
  const price = `${formatUsd(settings.usdPerSecond)}/s`;

  return (
    <div className="stack">
      <label className="cluster check" htmlFor="animation-auto">
        <input
          id="animation-auto"
          type="checkbox"
          checked={animation.auto}
          onChange={(e) => animation.setAuto(e.target.checked)}
        />
        <span className="hint">
          Animar cada imagen nueva con {settings.name}: el clip arranca en la imagen y dura lo que su
          tramo (de 3 a 15 s). Cuesta unos {price} a {settings.resolution}.
        </span>
      </label>
      {pending.length > 0 && (
        <button className="btn btn--block" onClick={actions.animateAll}>
          Animar {pending.length === 1 ? "la escena con imagen" : `las ${pending.length} escenas con imagen`}{" "}
          (≈ {formatUsd(estimateCost(pending, settings.usdPerSecond))})
        </button>
      )}
    </div>
  );
}
