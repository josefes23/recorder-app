"use client";

import { useState } from "react";

import { clipSeconds, formatUsd } from "@/domain/animation";
import { animatable } from "@/domain/scene";
import { TRANSITIONS, isTransitionKind, type Transition, type TransitionKind } from "@/domain/transition";
import { useAnimation } from "@/features/animation/model/use-animation";
import { useProduction } from "@/features/production/model/use-production";
import { useScenes, useTimeline } from "@/features/scenes/model/use-scenes";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";
import { ConfirmButton } from "@/shared/ui/ConfirmButton";

import { DurationSelect } from "./TransitionPicker";

type Props = {
  /** Las escenas marcadas, por posición. */
  marked: number[];
  onClear: () => void;
};

/**
 * Lo que se hace con varias escenas a la vez: la misma transición, animarlas
 * (con el precio antes de confirmar) o quitarlas.
 */
export function BulkBar({ marked, onClear }: Props) {
  const scenes = useScenes();
  const timeline = useTimeline();
  const animation = useAnimation();
  const actions = useStudioActions();
  const { transition: fallback } = useProduction();
  /** "" = volver a la del video. */
  const [kind, setKind] = useState<TransitionKind | "">("fundido");
  const [seconds, setSeconds] = useState(fallback.seconds);

  const label = marked.length === 1 ? "1 escena" : `${marked.length} escenas`;
  const toAnimate = marked.filter((i) => scenes.items[i] && animatable(scenes.items[i]));
  const usd = toAnimate.reduce((sum, i) => sum + clipSeconds(timeline.segments[i]?.span ?? 0), 0) * (animation.settings?.usdPerSecond ?? 0);
  const chosen: Transition | null = kind ? { kind, seconds } : null;

  return (
    <div className="bulk" role="region" aria-label="Acciones sobre las escenas marcadas">
      <strong className="bulk-count">{label}</strong>

      <div className="cluster">
        <select
          aria-label="Transición para las marcadas"
          value={kind}
          onChange={(e) => setKind(isTransitionKind(e.target.value) ? e.target.value : "")}
        >
          <option value="">Como el video</option>
          {TRANSITIONS.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
        {kind && kind !== "corte" && (
          <DurationSelect value={seconds} label="Duración de la transición para las marcadas" onChange={setSeconds} />
        )}
        <button type="button" className="btn btn--sm" onClick={() => scenes.setTransitionOn(marked, chosen)}>
          Aplicar transición
        </button>
      </div>

      <div className="cluster">
        {animation.ready && toAnimate.length > 0 && (
          <ConfirmButton
            confirm={`Confirmar · ≈ ${formatUsd(usd)}`}
            title="Cada segundo animado se paga: pide confirmación con el precio"
            onConfirm={() => {
              void actions.animateScenes(toAnimate);
              onClear();
            }}
          >
            Animar {toAnimate.length === marked.length ? "" : `${toAnimate.length} `}· ≈ {formatUsd(usd)}
          </ConfirmButton>
        )}
        <ConfirmButton
          className="btn btn--sm btn--danger"
          confirm={`¿Quitar ${label}?`}
          onConfirm={() => {
            scenes.removeMany(marked);
            onClear();
          }}
        >
          Quitar
        </ConfirmButton>
        <button type="button" className="btn btn--sm" onClick={onClear}>
          Desmarcar
        </button>
      </div>
    </div>
  );
}
