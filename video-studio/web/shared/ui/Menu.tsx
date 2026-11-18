"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

export type MenuItem = {
  label: string;
  onSelect: () => void;
  /** Borra o quita algo: se pinta en rojo. */
  danger?: boolean;
  disabled?: boolean;
  hint?: string;
};

type Props = {
  /** Lo que lee un lector de pantalla y el tooltip: «Más acciones de la escena 3». */
  label: string;
  items: MenuItem[];
};

/**
 * Las acciones que se usan poco, detrás de «⋯»: así no compiten con las de
 * todos los días. Se maneja con teclado (flechas, Inicio, Fin, Escape) y se
 * cierra al pulsar fuera.
 */
export function Menu({ label, items }: Props) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);

  /* Se abre hacia la izquierda, alineado al «⋯»; si así se sale de la
     pantalla (una tarjeta pegada al borde), hacia la derecha. Se mide antes de
     pintar, así que nunca se ve en el sitio equivocado. */
  useLayoutEffect(() => {
    const el = list.current;
    if (!open || !el) return;
    el.classList.remove("is-start");
    if (el.getBoundingClientRect().left < 0) el.classList.add("is-start");
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const away = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", away);
    root.current?.querySelector<HTMLButtonElement>('[role="menuitem"]:not(:disabled)')?.focus();
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const entries = [
      ...(root.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)') ?? []),
    ];
    const at = entries.indexOf(document.activeElement as HTMLButtonElement);
    const go = (index: number) => entries[(index + entries.length) % entries.length]?.focus();
    if (event.key === "Escape") {
      setOpen(false);
      trigger.current?.focus();
    } else if (event.key === "ArrowDown") go(at + 1);
    else if (event.key === "ArrowUp") go(at - 1);
    else if (event.key === "Home") go(0);
    else if (event.key === "End") go(entries.length - 1);
    else if (event.key === "Tab") setOpen(false);
    else return;
    if (event.key !== "Tab") event.preventDefault();
  };

  return (
    <div className="menu" ref={root} onKeyDown={open ? onKeyDown : undefined}>
      <button
        ref={trigger}
        type="button"
        className="btn btn--sm menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-label={label}
        title={label}
        onClick={() => setOpen((value) => !value)}
      >
        ⋯
      </button>
      {open && (
        <div className="menu-list" role="menu" id={id} aria-label={label} ref={list}>
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              className={`menu-item${item.danger ? " is-danger" : ""}`}
              disabled={item.disabled}
              title={item.hint}
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
