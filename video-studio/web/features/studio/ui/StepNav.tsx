"use client";

import type { CSSProperties } from "react";

import { foldable, nextStep, type StepState } from "@/domain/steps";
import { useStepStates } from "@/features/studio/model/use-step-states";
import { stepAnchor, useSteps } from "@/shared/ui/steps";

const ICON: Record<StepState, string> = { done: "✓", warn: "!", busy: "◌", todo: "•", optional: "○" };
const SAYS: Record<StepState, string> = {
  done: "listo",
  warn: "por revisar",
  busy: "en curso",
  todo: "pendiente",
  optional: "opcional",
};

/**
 * El índice de los pasos, siempre a la vista: en qué punto está cada uno y un
 * salto directo. Plegar los listos deja a la vista solo lo que falta.
 */
export function StepNav() {
  const steps = useStepStates();
  const ui = useSteps();
  const ready = foldable(steps);
  const next = nextStep(steps);
  const anyFolded = (ui?.folded.size ?? 0) > 0;

  return (
    <nav className="step-nav" aria-label="Pasos">
      <ol className="step-links">
        {steps.map((step) => (
          <li key={step.n}>
            <a
              href={`#${stepAnchor(step.n)}`}
              className={`step-link is-${step.state}${ui?.current === step.n ? " is-current" : ""}${next.kind !== "render" && next.n === step.n ? " is-next" : ""}`}
              style={{ "--hue": `var(--step-${step.n})` } as CSSProperties}
              aria-current={ui?.current === step.n ? "step" : undefined}
              title={`${step.title}: ${step.note || SAYS[step.state]}${next.kind !== "render" && next.n === step.n ? ` · ${next.message}` : ""}`}
              onClick={() => ui?.unfold(step.n)}
            >
              <span className="step-link-icon" aria-hidden="true">
                {ICON[step.state]}
              </span>
              <span className="step-link-n num">{step.n}</span>
              <span className="step-link-title">{step.title}</span>
              <span className="visually-hidden">, {step.note || SAYS[step.state]}</span>
            </a>
          </li>
        ))}
      </ol>
      {ui && (
        <button
          type="button"
          className="btn btn--sm step-nav-fold"
          disabled={!anyFolded && ready.length === 0}
          onClick={() => (anyFolded ? ui.unfoldAll() : ui.fold(ready))}
          title={anyFolded ? "Abrir todos los pasos" : "Plegar los pasos que ya están listos"}
        >
          {anyFolded ? "Desplegar todo" : "Plegar listos"}
        </button>
      )}
    </nav>
  );
}
