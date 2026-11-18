"use client";

import { useMemo, useState } from "react";

import {
  DEFAULT_FILTER,
  LIBRARY_PAGE,
  countByStatus,
  dayLabel,
  filterVideos,
  isPlayable,
  videoFormat,
  type LibraryFilter,
  type StatusFilter,
} from "@/domain/library";
import { useLibrary } from "@/features/library/model/use-library";
import { useFreshStart } from "@/features/studio/model/use-fresh-start";
import { Lightbox } from "@/shared/ui/Lightbox";

import { LibraryCard } from "./LibraryCard";

const STATUSES: { id: StatusFilter; label: string }[] = [
  { id: "all", label: "Todos" },
  { id: "done", label: "Listos" },
  { id: "failed", label: "Con fallos" },
  { id: "active", label: "En curso" },
];

/**
 * Los videos ya hechos, como una cuadrícula de portadas: se reconocen por lo
 * que se publicó. Con decenas de videos, se buscan y filtran, y se enseñan de
 * doce en doce. Cada portada sale pequeña y guardada en el servidor; el video
 * solo se carga al abrirlo.
 */
export function LibraryPanel() {
  const library = useLibrary();
  const { reuse } = useFreshStart();
  const [filter, setFilter] = useState<LibraryFilter>(DEFAULT_FILTER);
  const [shown, setShown] = useState(LIBRARY_PAGE);
  /** El video abierto en el reproductor, por id. */
  const [open, setOpen] = useState<number | null>(null);

  const counts = useMemo(() => countByStatus(library.items), [library.items]);
  const found = useMemo(() => filterVideos(library.items, filter), [library.items, filter]);
  const formats = useMemo(() => new Set(library.items.map(videoFormat)), [library.items]);
  const visible = found.slice(0, shown);
  const filtered = filter.query.trim() !== "" || filter.status !== "all" || filter.format !== "all";

  // Cambiar el filtro vuelve a la primera página.
  const refine = (changes: Partial<LibraryFilter>) => {
    setFilter((prev) => ({ ...prev, ...changes }));
    setShown(LIBRARY_PAGE);
  };

  // El reproductor pasa de uno a otro entre los que se pueden ver, con el filtro de ahora.
  const playable = found.filter(isPlayable);
  const at = playable.findIndex((item) => item.id === open);
  const current = at >= 0 ? playable[at] : undefined;

  return (
    <section className="panel panel--loose stack" id="biblioteca" aria-labelledby="biblioteca-titulo">
      <div className="spread">
        <h2 className="panel-title" id="biblioteca-titulo">
          Biblioteca
        </h2>
        {library.items.length > 0 && (
          <span className="hint">
            {counts.all === 1 ? "1 video" : `${counts.all} videos`}
          </span>
        )}
      </div>

      {library.items.length === 0 ? (
        <p className="hint">Aquí aparecerán los videos en cuanto renderices el primero.</p>
      ) : (
        <>
          <div className="lib-toolbar">
            <input
              type="search"
              className="lib-search"
              value={filter.query}
              placeholder="Buscar por tema, guion o descripción"
              aria-label="Buscar en la biblioteca"
              onChange={(e) => refine({ query: e.target.value })}
            />
            <div className="tabs lib-status-tabs" role="group" aria-label="Filtrar por estado">
              {STATUSES.filter((s) => s.id !== "active" || counts.active > 0).map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`tab${filter.status === s.id ? " is-on" : ""}`}
                  aria-pressed={filter.status === s.id}
                  onClick={() => refine({ status: s.id })}
                >
                  {s.label} <span className="num">{counts[s.id]}</span>
                </button>
              ))}
            </div>
            {formats.size > 1 && (
              <select
                className="lib-format"
                aria-label="Filtrar por formato"
                value={filter.format}
                onChange={(e) => refine({ format: e.target.value as LibraryFilter["format"] })}
              >
                <option value="all">Todos los formatos</option>
                <option value="9:16">Vertical 9:16</option>
                <option value="16:9">Horizontal 16:9</option>
              </select>
            )}
          </div>

          {found.length === 0 ? (
            <div className="cluster">
              <p className="hint">Ningún video coincide con la búsqueda.</p>
              <button type="button" className="btn btn--sm" onClick={() => refine(DEFAULT_FILTER)}>
                Quitar filtros
              </button>
            </div>
          ) : (
            <>
              {filtered && (
                <p className="hint" role="status">
                  {found.length === 1 ? "1 video" : `${found.length} videos`} con este filtro
                </p>
              )}
              <div className="library">
                {visible.map((item) => (
                  <LibraryCard key={item.id} item={item} onOpen={() => setOpen(item.id)} />
                ))}
              </div>
              {found.length > shown && (
                <button type="button" className="btn btn--block" onClick={() => setShown((n) => n + LIBRARY_PAGE)}>
                  Ver más · quedan {found.length - shown}
                </button>
              )}
            </>
          )}
        </>
      )}

      {current && (
        <Lightbox
          id={`video-${current.id}`}
          media={{ kind: "video", src: library.videoUrl(current.id), poster: library.posterUrl(current), player: true }}
          info={
            <>
              <strong>{current.topic}</strong> · {dayLabel(current.created_at)}
            </>
          }
          actions={
            <>
              <a className="btn" href={library.videoUrl(current.id)} download>
                Descargar
              </a>
              <button
                className="btn"
                onClick={() => {
                  // La vista se cierra solo si se carga: si se cancela, sigue donde estaba.
                  void reuse(current).then((loaded) => loaded && setOpen(null));
                }}
              >
                Reutilizar
              </button>
            </>
          }
          onPrev={at > 0 ? () => setOpen(playable[at - 1].id) : undefined}
          onNext={at < playable.length - 1 ? () => setOpen(playable[at + 1].id) : undefined}
          onClose={() => setOpen(null)}
        />
      )}
    </section>
  );
}
