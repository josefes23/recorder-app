"use client";

import { useId, useState, type ReactNode } from "react";

type Props = {
  /** Qué explica, para el lector de pantalla y el tooltip. */
  label?: string;
  children: ReactNode;
};

/**
 * Una explicación que no hace falta leer cada vez: detrás de un «?», a mano
 * cuando se necesita. Va dentro de una fila flexible (`.cluster`, `.spread`):
 * el texto se abre debajo, a todo el ancho.
 */
export function Help({ label = "Cómo funciona", children }: Props) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <>
      <button
        type="button"
        className="help"
        aria-expanded={open}
        aria-controls={id}
        aria-label={label}
        title={label}
        onClick={() => setOpen((value) => !value)}
      >
        ?
      </button>
      <p className="hint help-body" id={id} hidden={!open}>
        {children}
      </p>
    </>
  );
}
