"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

export type SelectOption = {
  value: string;
  label: string;
  /** Encabezado bajo el que se agrupa; las opciones del mismo grupo deben ir seguidas. */
  group?: string;
};

type Props = {
  /** Mismo `id` que la etiqueta del `Field`: así se enfoca al pulsarla. */
  id: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
};

/**
 * Un desplegable con la piel de la app, para listas largas o con grupos, donde
 * el `<select>` del sistema no se deja pintar. Hace lo que se espera de uno:
 * flechas, Inicio, Fin, Enter, Escape y escribir para saltar a una opción; se
 * cierra al pulsar fuera y se abre hacia arriba si abajo no cabe.
 */
export function Select({ id, value, options, onChange, disabled }: Props) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const typed = useRef({ text: "", at: 0 });

  const selected = options.findIndex((o) => o.value === value);
  const current = options[selected];

  const openList = () => {
    setActive(Math.max(selected, 0));
    setOpen(true);
  };
  const close = (refocus = true) => {
    setOpen(false);
    if (refocus) trigger.current?.focus();
  };
  const choose = (index: number) => {
    const option = options[index];
    if (option) onChange(option.value);
    close();
  };

  /* Se abre hacia arriba si abajo no hay sitio; se mide antes de pintar. */
  useLayoutEffect(() => {
    const el = list.current;
    if (!open || !el) return;
    el.classList.remove("is-up");
    const box = el.getBoundingClientRect();
    if (box.bottom > window.innerHeight && trigger.current && trigger.current.getBoundingClientRect().top > box.height) {
      el.classList.add("is-up");
    }
  }, [open]);

  /* La opción activa siempre a la vista. */
  useEffect(() => {
    if (open) list.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  useEffect(() => {
    if (!open) return;
    const away = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);

  const jumpTo = (key: string) => {
    const now = Date.now();
    const state = typed.current;
    state.text = now - state.at > 700 ? key.toLowerCase() : state.text + key.toLowerCase();
    state.at = now;
    const from = state.text.length === 1 ? active + 1 : active;
    const ordered = [...options.keys()].map((i) => (i + from) % options.length);
    const hit = ordered.find((i) => options[i].label.toLowerCase().startsWith(state.text));
    if (hit !== undefined) setActive(hit);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled || !options.length) return;
    const last = options.length - 1;
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
        event.preventDefault();
        openList();
      }
      return;
    }
    switch (event.key) {
      case "ArrowDown": setActive((a) => Math.min(a + 1, last)); break;
      case "ArrowUp": setActive((a) => Math.max(a - 1, 0)); break;
      case "Home": setActive(0); break;
      case "End": setActive(last); break;
      case "Enter":
      case " ": choose(active); break;
      case "Escape": close(); break;
      case "Tab": setOpen(false); return;
      default:
        if (event.key.length === 1 && !event.ctrlKey && !event.metaKey) jumpTo(event.key);
        return;
    }
    event.preventDefault();
  };

  return (
    <div ref={root} className={`select${open ? " is-open" : ""}`}>
      <button
        ref={trigger}
        id={id}
        type="button"
        className="select-trigger"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        disabled={disabled}
        onClick={() => (open ? close(false) : openList())}
        onKeyDown={onKeyDown}
      >
        <span className="select-value">{current?.label ?? "—"}</span>
        <svg className="select-chevron" width="12" height="8" viewBox="0 0 12 8" fill="none" aria-hidden="true">
          <path d="M1.5 1.75 6 6.25l4.5-4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div ref={list} id={listId} role="listbox" className="select-list">
          {options.map((option, index) => (
            <div key={option.value}>
              {option.group && option.group !== options[index - 1]?.group && (
                <div className="select-group" role="presentation">{option.group}</div>
              )}
              <div
                role="option"
                aria-selected={index === selected}
                data-active={index === active}
                className={`select-option${index === active ? " is-active" : ""}`}
                onPointerEnter={() => setActive(index)}
                onClick={() => choose(index)}
              >
                <span>{option.label}</span>
                {index === selected && <span className="select-check" aria-hidden="true">✓</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
