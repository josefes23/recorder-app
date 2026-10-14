"use client";

import type { ReactNode } from "react";

type Props = {
  summary: string;
  /** Resumen de lo que hay dentro, para no tener que abrirlo por curiosidad. */
  note?: ReactNode;
  children: ReactNode;
};

/** Lo que se ajusta una vez y no se vuelve a mirar va aquí dentro. */
export function Disclosure({ summary, note, children }: Props) {
  return (
    <details className="disclosure">
      <summary>
        {summary}
        {note !== undefined && <span className="hint">{note}</span>}
      </summary>
      <div className="disclosure-body">{children}</div>
    </details>
  );
}
