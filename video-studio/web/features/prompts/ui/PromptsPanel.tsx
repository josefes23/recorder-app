"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { GROUP_LABELS, byGroup, type PromptInfo, type PromptPreview } from "@/domain/prompts";
import { usePrompts } from "@/features/prompts/model/use-prompts";

/**
 * Los prompts que se mandan por debajo, para leerlos y cambiarlos. Cada uno es
 * una plantilla: el texto se edita y las {variables} las rellena el programa.
 * Mientras se edita se ve el prompt ya montado con datos de ejemplo.
 */
export function PromptsPanel({ onClose }: { onClose: () => void }) {
  const prompts = usePrompts();
  const { items, load, save, reset, preview } = prompts;
  const [picked, setPicked] = useState<string | null>(null);
  /** Lo escrito y aún sin guardar, por prompt: cambiar de uno no lo pierde. */
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [live, setLive] = useState<{ id: string; text: string; result: PromptPreview } | null>(null);
  const area = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const unsaved = (p: PromptInfo) => drafts[p.id] !== undefined && drafts[p.id] !== p.text;
  const current: PromptInfo | undefined = items.find((p) => p.id === picked) ?? items[0];
  const draft = current ? (drafts[current.id] ?? current.text) : "";
  const dirty = current !== undefined && draft !== current.text;

  /* El ejemplo de lo que se está escribiendo, medio segundo después de parar. */
  useEffect(() => {
    if (!current || !dirty) return;
    const { id } = current;
    const timer = setTimeout(async () => {
      const result = await preview(id, draft);
      if (result) setLive({ id, text: draft, result });
    }, 450);
    return () => clearTimeout(timer);
  }, [current, dirty, draft, preview]);

  const shown = useMemo(() => {
    if (!current) return null;
    if (dirty && live && live.id === current.id && live.text === draft) return live.result;
    return { examples: current.examples, warnings: current.warnings };
  }, [current, dirty, draft, live]);

  const setDraft = (text: string) => current && setDrafts((prev) => ({ ...prev, [current.id]: text }));
  const clearDraft = () =>
    current &&
    setDrafts((prev) => Object.fromEntries(Object.entries(prev).filter(([id]) => id !== current.id)));

  const insert = (name: string) => {
    const box = area.current;
    const token = `{${name}}`;
    if (!box) return setDraft(draft + token);
    const { selectionStart: from, selectionEnd: to } = box;
    setDraft(draft.slice(0, from) + token + draft.slice(to));
    requestAnimationFrame(() => {
      box.focus();
      box.setSelectionRange(from + token.length, from + token.length);
    });
  };

  /* En el body y no en la barra: la barra es pegajosa y un `fixed` dentro de ella
     se coloca respecto a ella, no a la ventana. */
  return createPortal(
    <div className="modal" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <section className="modal-box prompts" role="dialog" aria-modal="true" aria-label="Prompts">
        <header className="modal-head">
          <h2>Prompts</h2>
          <span className="hint">
            Lo que se manda por debajo a los modelos. Las <code>{"{variables}"}</code> las rellena el programa
            con los datos de cada video.
          </span>
          <button className="btn btn--sm" onClick={onClose}>
            Cerrar
          </button>
        </header>

        <div className="prompts-body">
          <nav className="prompts-list" aria-label="Prompts">
            {byGroup(items).map(({ group, items: entries }) => (
              <div key={group}>
                <p className="prompts-group">{GROUP_LABELS[group]}</p>
                {entries.map((p) => (
                  <button
                    key={p.id}
                    className={`prompts-item${p.id === current?.id ? " is-active" : ""}`}
                    onClick={() => setPicked(p.id)}
                  >
                    {p.name}
                    {unsaved(p) ? (
                      <span className="chip is-on">sin guardar</span>
                    ) : (
                      p.edited && <span className="chip is-on">editado</span>
                    )}
                  </button>
                ))}
              </div>
            ))}
          </nav>

          {current && shown && (
            <div className="prompts-editor">
              <div>
                <h3>{current.name}</h3>
                <p className="hint">{current.when}</p>
                {current.user_part && (
                  <p className="hint">Además se envía, aparte y sin poder editarse: {current.user_part}</p>
                )}
              </div>

              {current.variables.length > 0 && (
                <div className="cluster">
                  <span className="hint">Variables (pulsa para insertar):</span>
                  {current.variables.map((v) => (
                    <button key={v.name} className="chip" title={v.help} onClick={() => insert(v.name)}>
                      {`{${v.name}}`}
                    </button>
                  ))}
                </div>
              )}

              <textarea
                ref={area}
                className="prompts-text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                spellCheck={false}
                rows={16}
                aria-label={`Texto del prompt «${current.name}»`}
              />

              {shown.warnings.map((w) => (
                <p key={w} className="hint warn">
                  {w}
                </p>
              ))}

              <div className="cluster">
                <button
                  className="btn btn--primary"
                  disabled={!dirty}
                  onClick={async () => (await save(current.id, draft)) && clearDraft()}
                >
                  Guardar
                </button>
                <button className="btn" disabled={!dirty} onClick={clearDraft}>
                  Descartar cambios
                </button>
                <button
                  className="btn"
                  disabled={!current.edited && draft === current.default}
                  onClick={async () => (await reset(current.id)) && clearDraft()}
                >
                  Restaurar el original
                </button>
                <span className="hint">
                  {dirty ? "Cambios sin guardar." : current.edited ? "Editado: se usa tu versión." : "Es el original."}
                </span>
              </div>

              <div className="prompts-examples">
                <p className="prompts-group">Así se envía, con datos de ejemplo</p>
                {shown.examples.map((example) => (
                  <figure key={example.label}>
                    <figcaption className="hint">{example.label}</figcaption>
                    <pre>{example.text}</pre>
                  </figure>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>,
    document.body,
  );
}
