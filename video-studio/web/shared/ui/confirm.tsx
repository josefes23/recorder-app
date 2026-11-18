"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

export type ConfirmOptions = {
  title: string;
  /** Qué se pierde, en lenguaje llano. Una línea por elemento de la lista. */
  message: string;
  details?: string[];
  confirmLabel: string;
};

type Ask = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<Ask | null>(null);

/**
 * Pregunta antes de una acción que borra trabajo. Se pide con `await confirm()`
 * y devuelve si el usuario aceptó. El foco empieza en «Cancelar»: un Enter de
 * más no debe tirar lo hecho.
 */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<{ options: ConfirmOptions; settle: (ok: boolean) => void } | null>(null);

  const ask = useCallback<Ask>(
    (options) =>
      new Promise<boolean>((resolve) => {
        // Una pregunta nueva cancela la anterior: nunca quedan dos abiertas.
        setPending((previous) => {
          previous?.settle(false);
          return { options, settle: resolve };
        });
      }),
    [],
  );

  const answer = useCallback(
    (ok: boolean) => {
      pending?.settle(ok);
      setPending(null);
    },
    [pending],
  );

  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!pending) return;
    cancel.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && answer(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pending, answer]);

  const value = useMemo(() => ask, [ask]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {pending &&
        // En el body: la barra es pegajosa y un `fixed` dentro de ella se coloca respecto a ella.
        createPortal(
          <div className="confirm" onClick={(e) => e.target === e.currentTarget && answer(false)}>
            <section className="confirm-box" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
              <h2 id="confirm-title">{pending.options.title}</h2>
              <p>{pending.options.message}</p>
              {pending.options.details && pending.options.details.length > 0 && (
                <ul>
                  {pending.options.details.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              )}
              <div className="cluster confirm-actions">
                <button ref={cancel} className="btn" onClick={() => answer(false)}>
                  Cancelar
                </button>
                <button className="btn btn--primary" onClick={() => answer(true)}>
                  {pending.options.confirmLabel}
                </button>
              </div>
            </section>
          </div>,
          document.body,
        )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): Ask {
  const ask = useContext(ConfirmContext);
  if (!ask) throw new Error("useConfirm va dentro de <ConfirmProvider>.");
  return ask;
}
