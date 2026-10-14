"use client";

import type { ReactNode } from "react";

type Props = {
  id: string;
  label: string;
  /** Valor actual, a la derecha de la etiqueta y en cifras de ancho fijo. */
  value?: ReactNode;
  children: ReactNode;
};

export function Field({ id, label, value, children }: Props) {
  return (
    <div className="field">
      <label htmlFor={id}>
        <span>{label}</span>
        {value !== undefined && <b className="num">{value}</b>}
      </label>
      {children}
    </div>
  );
}
