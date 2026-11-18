"use client";

import { useEffect, useState, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  /** Lo que dice al pedir la confirmación: «¿Quitar 3 escenas?», «Confirmar · US$ 1,20». */
  confirm: ReactNode;
  onConfirm: () => void;
  className?: string;
  disabled?: boolean;
  title?: string;
};

/** Cuánto espera la confirmación antes de volver a su estado normal. */
const ARMED_MS = 4000;

/**
 * Un botón que pide una segunda pulsación para lo que borra o cuesta dinero,
 * en el sitio y sin la ventana del navegador, que bloquea toda la página.
 */
export function ConfirmButton({ children, confirm, onConfirm, className = "btn btn--sm", disabled, title }: Props) {
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    if (!armed) return;
    const timer = setTimeout(() => setArmed(false), ARMED_MS);
    return () => clearTimeout(timer);
  }, [armed]);

  return (
    <button
      type="button"
      className={`${className}${armed ? " is-armed" : ""}`}
      disabled={disabled}
      title={title}
      aria-live="polite"
      onClick={() => {
        if (!armed) return setArmed(true);
        setArmed(false);
        onConfirm();
      }}
      onBlur={() => setArmed(false)}
    >
      {armed ? confirm : children}
    </button>
  );
}
