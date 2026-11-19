"use client";

import { useEffect, useRef, type CSSProperties, type ReactNode } from "react";

import { stepAnchor, useSteps } from "./steps";

type Props = {
  /** Número de fase. El orden es real: la duración del guion condiciona el resto. */
  n: number;
  title: string;
  /** Para qué sirve el paso, en una línea: quien se pierde lo lee aquí. */
  lead?: string;
  /** Estado derivado del paso, alineado a la derecha. Nunca repite un control visible. */
  note?: ReactNode;
  children: ReactNode;
};

/**
 * Un paso del estudio: una tarjeta con su color, su número grande y una línea
 * que dice para qué sirve. El título lo pliega y despliega: plegado queda solo
 * su cabecera con la nota, que resume lo que hay dentro. El paso que se está
 * mirando se marca como el actual.
 */
export function Step({ n, title, lead, note, children }: Props) {
  const steps = useSteps();
  const folded = steps?.folded.has(n) ?? false;
  const current = steps?.current === n;
  const anchor = stepAnchor(n);
  const root = useRef<HTMLElement>(null);
  const setCurrent = steps?.setCurrent;

  /* El actual es el que cruza una franja un poco por encima del centro de la
     pantalla: así cambia al desplazarse, sin esperar a que se toque nada. */
  useEffect(() => {
    const el = root.current;
    if (!el || !setCurrent || typeof IntersectionObserver === "undefined") return;
    const watcher = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setCurrent(n);
      },
      { rootMargin: "-30% 0px -60% 0px" },
    );
    watcher.observe(el);
    return () => watcher.disconnect();
  }, [n, setCurrent]);

  return (
    <section
      ref={root}
      className={`step${folded ? " is-folded" : ""}${current ? " is-current" : ""}`}
      id={anchor}
      style={{ "--hue": `var(--step-${n})` } as CSSProperties}
      aria-labelledby={`${anchor}-titulo`}
      aria-current={current ? "step" : undefined}
      onFocusCapture={() => setCurrent?.(n)}
    >
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
            <span className="step-name">{title}</span>
            <span className="step-caret" aria-hidden="true">
              ▾
            </span>
          </button>
        </h2>
        {note !== undefined && <span className="step-note">{note}</span>}
      </div>
      {lead && !folded && <p className="step-lead">{lead}</p>}
      <div className="step-body" id={`${anchor}-cuerpo`} hidden={folded}>
        {children}
      </div>
    </section>
  );
}
