"use client";

import type { ReactNode } from "react";

import { stepAnchor, useSteps } from "./steps";

type Props = {
  /** Número de fase. El orden es real: la duración del guion condiciona el resto. */
  n: number;
  title: string;
  /** Estado derivado del paso, alineado a la derecha. Nunca repite un control visible. */
  note?: ReactNode;
  children: ReactNode;
};

/**
 * Un paso del estudio. El título lo pliega y despliega: plegado queda solo su
 * cabecera con la nota, que resume lo que hay dentro.
 */
export function Step({ n, title, note, children }: Props) {
  const steps = useSteps();
  const folded = steps?.folded.has(n) ?? false;
  const anchor = stepAnchor(n);

  return (
    <section className={`step${folded ? " is-folded" : ""}`} id={anchor} aria-labelledby={`${anchor}-titulo`}>
      <div className="step-head">
        <h2 className="step-title" id={`${anchor}-titulo`}>
          <button
            type="button"
            className="step-toggle"
            aria-expanded={!folded}
            aria-controls={`${anchor}-cuerpo`}
            onClick={() => steps?.toggle(n)}
            disabled={!steps}
          >
            <span className="step-n">{n}</span>
            {title}
            <span className="step-caret" aria-hidden="true">
              ▾
            </span>
          </button>
        </h2>
        {note !== undefined && <span className="step-note">{note}</span>}
      </div>
      <div className="step-body" id={`${anchor}-cuerpo`} hidden={folded}>
        {children}
      </div>
    </section>
  );
}
