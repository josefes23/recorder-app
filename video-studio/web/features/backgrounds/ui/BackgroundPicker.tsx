"use client";

import { useRef, useState } from "react";

import { describeDownload } from "@/domain/stock";
import { useBackgrounds } from "@/features/backgrounds/model/use-backgrounds";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { Lightbox } from "@/shared/ui/Lightbox";

type Props = {
  /** Qué hacer con el fondo elegido lo decide quien abre el diálogo. */
  onSelect: (name: string) => void;
  onClose: () => void;
};

/** Qué hay abierto a tamaño grande: un resultado de Pexels o un fondo de la galería. */
type Peek = { of: "results" | "gallery"; index: number };

export function BackgroundPicker({ onSelect, onClose }: Props) {
  const backgrounds = useBackgrounds();
  const { deleteBackground } = useStudioActions();
  const { busy, error } = useStatus();
  const [query, setQuery] = useState("");
  const [chosen, setChosen] = useState<Set<number>>(() => new Set());
  const [peek, setPeek] = useState<Peek | null>(null);
  const [note, setNote] = useState("");
  /* El error es global; aquí solo interesa si lo provocó algo de este diálogo. */
  const [acted, setActed] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const working = busy !== null;
  const { results, items } = backgrounds;
  const peekedClip = peek?.of === "results" && results ? results.clips[peek.index] : undefined;
  const peekedItem = peek?.of === "gallery" ? items[peek.index] : undefined;

  const search = async () => {
    setActed(true);
    setNote("");
    setChosen(new Set());
    setPeek(null);
    await backgrounds.search(query);
  };

  const toggle = (id: number) =>
    setChosen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const download = async () => {
    setActed(true);
    setNote("Descargando…");
    const report = await backgrounds.download([...chosen]);
    setNote(report ? describeDownload(report) : "");
    if (report) setChosen(new Set());
  };

  const upload = async (file: File) => {
    setActed(true);
    setNote("Subiendo…");
    await backgrounds.upload(file);
    setNote("Subido.");
    if (fileRef.current) fileRef.current.value = "";
  };

  const remove = async (name: string) => {
    if (!window.confirm(`¿Borrar «${name}» de la galería? Se elimina el archivo.`)) return;
    setActed(true);
    setPeek(null);
    setNote("Borrando…");
    const ok = await deleteBackground(name);
    setNote(ok ? `Borrado ${name}.` : "");
  };

  return (
    <div className="modal" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <div className="spread">
          <h2 className="panel-title">Elegir fondo</h2>
          <button className="btn btn--sm" onClick={onClose}>
            Cerrar
          </button>
        </div>

        <div className="cluster cluster--search">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
            placeholder="Buscar en Pexels: sleeping bedroom, coffee…"
            autoComplete="off"
          />
          <button className="btn" onClick={search} disabled={working}>
            {busy === "search" ? "Buscando…" : "Buscar"}
          </button>
          <label className="btn">
            Subir archivo
            <input
              ref={fileRef}
              type="file"
              accept="video/*,image/*"
              hidden
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            />
          </label>
        </div>

        {acted && error && <p className="error">{error}</p>}
        {note && <p className="hint">{note}</p>}

        {results && (
          <section className="stock">
            <div className="spread">
              <p className="hint">
                {results.clips.length === 0 ? (
                  <>Pexels no tiene clips verticales para «{results.query}».</>
                ) : (
                  <>
                    {results.clips.length} clips en{" "}
                    <a href="https://www.pexels.com" target="_blank" rel="noreferrer">
                      Pexels
                    </a>{" "}
                    para «{results.query}». Marca los que quieras y descárgalos; «Ver» los
                    enseña grandes y en movimiento.
                  </>
                )}
              </p>
              {results.clips.length > 0 && (
                <button
                  className="btn btn--primary btn--sm"
                  onClick={download}
                  disabled={working || chosen.size === 0}
                >
                  {busy === "backgrounds"
                    ? "Descargando…"
                    : chosen.size
                      ? `Descargar ${chosen.size}`
                      : "Descargar"}
                </button>
              )}
            </div>

            <div className="gallery gallery--stock">
              {results.clips.map((clip, index) => {
                const selected = chosen.has(clip.id);
                return (
                  <figure
                    key={clip.id}
                    className={clip.owned ? "is-owned" : selected ? "is-selected" : undefined}
                    title={`${clip.width}×${clip.height} · ${clip.size_mb} MB · ${clip.author}`}
                    onClick={() => !clip.owned && toggle(clip.id)}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={clip.preview} alt="" loading="lazy" />
                    {clip.owned ? (
                      <span className="badge">En la galería</span>
                    ) : (
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggle(clip.id)}
                        onClick={(e) => e.stopPropagation()}
                        aria-label={`Descargar el clip de ${clip.author}`}
                      />
                    )}
                    <button
                      type="button"
                      className="peek"
                      onClick={(e) => {
                        e.stopPropagation();
                        setPeek({ of: "results", index });
                      }}
                      aria-label={`Ver grande el clip de ${clip.author}`}
                    >
                      Ver
                    </button>
                    <figcaption>
                      {clip.duration}s · {clip.author}
                    </figcaption>
                  </figure>
                );
              })}
            </div>
          </section>
        )}

        {results && <h3 className="panel-title">Tu galería</h3>}
        <div className="gallery">
          {items.length === 0 ? (
            <p className="hint">No hay fondos todavía. Busca en Pexels o sube un archivo.</p>
          ) : (
            items.map((bg, index) => (
              <figure key={bg.name} onClick={() => onSelect(bg.name)} title="Usar este fondo">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={backgrounds.thumbUrl(bg.thumb)} alt="" loading="lazy" />
                <button
                  type="button"
                  className="peek peek--delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    remove(bg.name);
                  }}
                  disabled={working}
                  title="Borrar de la galería"
                  aria-label={`Borrar ${bg.name}`}
                >
                  ×
                </button>
                <button
                  type="button"
                  className="peek"
                  onClick={(e) => {
                    e.stopPropagation();
                    setPeek({ of: "gallery", index });
                  }}
                  aria-label={`Ver grande ${bg.name}`}
                >
                  Ver
                </button>
                <figcaption>
                  {bg.group}
                  {bg.duration ? ` · ${bg.duration}s` : ""}
                </figcaption>
              </figure>
            ))
          )}
        </div>
      </div>

      {peek && peekedClip && results && (
        <Lightbox
          id={`stock-${peekedClip.id}`}
          media={{ kind: "video", src: peekedClip.play, poster: peekedClip.preview }}
          info={
            <>
              <strong>{peekedClip.author}</strong> · {peekedClip.duration}s ·{" "}
              {peekedClip.width}×{peekedClip.height} · {peekedClip.size_mb} MB ·{" "}
              <a href={peekedClip.url} target="_blank" rel="noreferrer">
                ver en Pexels
              </a>
            </>
          }
          actions={
            peekedClip.owned ? (
              <span className="hint">Ya está en tu galería.</span>
            ) : (
              <button
                className={chosen.has(peekedClip.id) ? "btn" : "btn btn--primary"}
                onClick={() => toggle(peekedClip.id)}
              >
                {chosen.has(peekedClip.id) ? "Quitar de la selección" : "Marcar para descargar"}
              </button>
            )
          }
          onPrev={peek.index > 0 ? () => setPeek({ of: "results", index: peek.index - 1 }) : undefined}
          onNext={
            peek.index < results.clips.length - 1
              ? () => setPeek({ of: "results", index: peek.index + 1 })
              : undefined
          }
          onClose={() => setPeek(null)}
        />
      )}

      {peek && peekedItem && (
        <Lightbox
          id={`gallery-${peekedItem.name}`}
          media={{
            kind: peekedItem.kind,
            src: backgrounds.fileUrl(peekedItem.name),
            poster: backgrounds.thumbUrl(peekedItem.thumb),
          }}
          info={
            <>
              <strong>{peekedItem.name}</strong>
              {peekedItem.duration ? ` · ${peekedItem.duration}s` : ""} · {peekedItem.size_mb} MB
            </>
          }
          actions={
            <>
              <button className="btn btn--primary" onClick={() => onSelect(peekedItem.name)}>
                Usar este fondo
              </button>
              <button className="btn" onClick={() => remove(peekedItem.name)} disabled={working}>
                Borrar de la galería
              </button>
            </>
          }
          onPrev={peek.index > 0 ? () => setPeek({ of: "gallery", index: peek.index - 1 }) : undefined}
          onNext={
            peek.index < items.length - 1
              ? () => setPeek({ of: "gallery", index: peek.index + 1 })
              : undefined
          }
          onClose={() => setPeek(null)}
        />
      )}
    </div>
  );
}
