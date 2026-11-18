"use client";

import {
  MAX_TRANSITION_SECONDS,
  MIN_TRANSITION_SECONDS,
  TRANSITIONS,
  TRANSITION_STEP,
  clampSeconds,
  describeTransition,
  isTransitionKind,
  type Transition,
} from "@/domain/transition";
import { useProduction } from "@/features/production/model/use-production";
import { useSceneMedia, useScenes } from "@/features/scenes/model/use-scenes";
import { Help } from "@/shared/ui/Help";
import { Slider } from "@/shared/ui/Slider";

import { TransitionPreview } from "./TransitionPreview";

const seconds = (value: number) => value.toLocaleString("es", { minimumFractionDigits: 1 });

/** Las duraciones que se pueden elegir, en décimas: 0,2 … 1,5 s. */
export const DURATIONS = Array.from(
  { length: Math.round((MAX_TRANSITION_SECONDS - MIN_TRANSITION_SECONDS) / TRANSITION_STEP) + 1 },
  (_, i) => clampSeconds(MIN_TRANSITION_SECONDS + i * TRANSITION_STEP),
);

/** La del video: la usan las escenas que no eligen otra. */
export function VideoTransition() {
  const production = useProduction();
  const scenes = useScenes();
  const media = useSceneMedia();
  const { transition } = production;
  const chosen = TRANSITIONS.find((t) => t.id === transition.kind) ?? TRANSITIONS[0];
  // La vista previa con las dos primeras imágenes del video, si las hay.
  const [first, second] = scenes.items.filter((s) => s.background).map((s) => media(s.background).thumb);

  return (
    <div className="transition-panel">
      <TransitionPreview from={first ?? null} to={second ?? null} transition={transition} wide={production.format === "16:9"} />
      <div className="stack transition-fields">
        <div className="spread">
          <label className="field-label" htmlFor="transition-kind">
            Transición del video
          </label>
          <Help label="Cómo funcionan las transiciones">
            {chosen.hint} La usan las escenas que no elijan otra, también al cambiar de encuadre
            dentro de una imagen fija. Va centrada en el cambio, así que cada imagen sigue entrando
            con su frase; si una escena dura menos que la transición, se acorta. En la barra, ◆ marca
            las escenas con una propia y ◇ las que usan esta: púlsalas para cambiarlas.
          </Help>
        </div>
        <select
          id="transition-kind"
          value={transition.kind}
          onChange={(e) =>
            isTransitionKind(e.target.value) && production.setTransition({ ...transition, kind: e.target.value })
          }
        >
          {TRANSITIONS.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
        {transition.kind !== "corte" && (
          <Slider
            id="transition-seconds"
            label="Duración"
            value={transition.seconds}
            display={`${seconds(transition.seconds)} s`}
            min={MIN_TRANSITION_SECONDS}
            max={MAX_TRANSITION_SECONDS}
            step={TRANSITION_STEP}
            onChange={(value) => production.setTransition({ ...transition, seconds: clampSeconds(value) })}
          />
        )}
      </div>
    </div>
  );
}

type SceneProps = {
  index: number;
  /** La suya, si eligió una. */
  transition?: Transition;
  /** La del video, para la opción «Como el video». */
  fallback: Transition;
  /** Para poder llevar el foco aquí desde la marca de la barra. */
  id?: string;
};

/** La de una escena: cómo entra y, si es una imagen fija, cómo cambia de encuadre. */
export function SceneTransition({ index, transition, fallback, id = `scene-transition-${index}` }: SceneProps) {
  const scenes = useScenes();
  // La primera no tiene de dónde entrar: solo cuenta para sus encuadres.
  const first = index === 0;

  return (
    <div className="field">
      <label htmlFor={id}>{first ? "Cambios de encuadre" : "Transición de entrada"}</label>
      <div className="scene-transition">
        <select
          id={id}
          value={transition?.kind ?? ""}
          title={
            first
              ? "La primera escena no tiene de dónde entrar: esto cambia cómo pasa de un encuadre a otro."
              : "Cómo entra esta escena y, si es una imagen fija, cómo cambia de encuadre."
          }
          onChange={(e) => {
            const kind = e.target.value;
            scenes.setTransition(
              index,
              isTransitionKind(kind) ? { kind, seconds: transition?.seconds ?? fallback.seconds } : null,
            );
          }}
        >
          <option value="">Como el video ({describeTransition(fallback)})</option>
          {TRANSITIONS.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
        {transition && transition.kind !== "corte" && (
          <DurationSelect
            value={transition.seconds}
            label={`Duración de la transición de la escena ${index + 1}`}
            onChange={(value) => scenes.setTransition(index, { ...transition, seconds: value })}
          />
        )}
      </div>
    </div>
  );
}

export function DurationSelect({ value, label, onChange }: { value: number; label: string; onChange: (value: number) => void }) {
  return (
    <select className="num" value={value} aria-label={label} onChange={(e) => onChange(clampSeconds(parseFloat(e.target.value)))}>
      {DURATIONS.map((option) => (
        <option key={option} value={option}>
          {seconds(option)} s
        </option>
      ))}
    </select>
  );
}
