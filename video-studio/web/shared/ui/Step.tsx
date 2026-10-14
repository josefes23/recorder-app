"use client";

import type { ReactNode } from "react";

type Props = {
  /** Número de fase. El orden es real: la duración del guion condiciona el resto. */
  n: number;
  title: string;
  /** Estado derivado del paso, alineado a la derecha. Nunca repite un control visible. */
  note?: ReactNode;
  children: ReactNode;
};

export function Step({ n, title, note, children }: Props) {
  return (
    <section className="step">
      <div className="step-head">
        <span className="step-n">{n}</span>
        <h2 className="step-title">{title}</h2>
        {note !== undefined && <span className="step-note">{note}</span>}
      </div>
      {children}
    </section>
  );
}
