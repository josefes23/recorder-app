"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  text: string;
  label: string;
  className?: string;
};

/** Copia al portapapeles y lo confirma un momento en el propio botón. */
export function CopyButton({ text, label, className = "btn btn--sm" }: Props) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text.trim());
      setState("copied");
    } catch {
      // Sin permiso de portapapeles: que se note, en vez de no hacer nada.
      setState("failed");
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), 1800);
  };

  return (
    <button className={className} disabled={!text.trim()} onClick={copy} aria-live="polite">
      {state === "copied" ? "Copiada ✓" : state === "failed" ? "No se pudo copiar" : label}
    </button>
  );
}
