"use client";

import { useEffect, useState } from "react";

import { clockTime, dayLabel, isPlayable, videoFormat, type VideoItem } from "@/domain/library";
import { useLibrary } from "@/features/library/model/use-library";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";
import { Menu, type MenuItem } from "@/shared/ui/Menu";

/** Descarga un archivo sin salir de la página: un enlace con `download`, pulsado por código. */
function download(href: string) {
  const link = document.createElement("a");
  link.href = href;
  link.download = "";
  document.body.append(link);
  link.click();
  link.remove();
}

const STATUS: Record<VideoItem["status"], string | null> = {
  queued: "En cola",
  running: "Renderizando",
  error: "Falló",
  done: null,
};

type Props = {
  item: VideoItem;
  /** Abrirlo en el reproductor. */
  onOpen: () => void;
};

/**
 * Un video de la biblioteca: su portada, qué es y cuándo se hizo. Lo de todos
 * los días (reutilizar, descargar) a la vista; lo demás en «⋯». Borrar pide
 * confirmación en la propia tarjeta.
 */
export function LibraryCard({ item, onOpen }: Props) {
  const library = useLibrary();
  const { reuse } = useStudioActions();
  /** La portada no llegó (un servidor anterior, un fallo al pintarla): se enseña el tema. */
  const [broken, setBroken] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 2500);
    return () => clearTimeout(timer);
  }, [notice]);

  const playable = isPlayable(item);
  const wide = videoFormat(item) === "16:9";
  const status = STATUS[item.status];
  const progress = item.status === "running" && item.progress ? ` ${Math.round(item.progress * 100)} %` : "";
  const description = item.description?.trim() ?? "";

  const more: MenuItem[] = [
    { label: "Descargar la portada", onSelect: () => download(library.coverUrl(item.id)), hint: "A tamaño completo, con su título" },
    ...(description
      ? [
          {
            label: "Copiar la descripción",
            onSelect: () =>
              navigator.clipboard
                .writeText(description)
                .then(() => setNotice("Descripción copiada"))
                .catch(() => setNotice("No se pudo copiar")),
          },
        ]
      : []),
    { label: "Borrar…", danger: true, onSelect: () => setConfirming(true) },
  ];

  return (
    <article className={`lib-card${item.status === "error" ? " is-failed" : ""}`}>
      <button
        type="button"
        className={`lib-poster${wide ? " is-wide" : ""}`}
        onClick={onOpen}
        disabled={!playable}
        aria-label={playable ? `Ver «${item.topic}»` : item.topic}
      >
        {broken ? (
          <span className="lib-poster-blank">{item.topic}</span>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={library.posterUrl(item)} alt="" loading="lazy" onError={() => setBroken(true)} />
        )}
        {playable && <span className="lib-play" aria-hidden="true">▶</span>}
        {playable && item.duration ? <span className="lib-duration num">{clockTime(item.duration)}</span> : null}
        {status && <span className={`lib-status is-${item.status}`}>{status + progress}</span>}
      </button>

      <div className="lib-card-body">
        <h3 title={item.topic}>{item.topic}</h3>
        <p className="hint">
          {dayLabel(item.created_at)}
          {playable && item.size_mb ? ` · ${item.size_mb} MB` : ""}
        </p>
        {item.error && (
          <p className="error lib-error" title={item.error}>
            {item.error}
          </p>
        )}
        {notice && (
          <p className="hint" role="status">
            {notice}
          </p>
        )}
      </div>

      {confirming ? (
        <div className="lib-confirm" role="group" aria-label="Confirmar el borrado">
          <span className="hint">¿Borrar el video y su archivo?</span>
          <div className="cluster">
            <button
              type="button"
              className="btn btn--sm btn--danger"
              autoFocus
              onClick={() => {
                setConfirming(false);
                void library.remove(item.id);
              }}
            >
              Borrar
            </button>
            <button type="button" className="btn btn--sm" onClick={() => setConfirming(false)}>
              Cancelar
            </button>
          </div>
        </div>
      ) : (
        <div className="lib-actions">
          <button type="button" className="btn btn--sm" onClick={() => reuse(item)} title="Cargar su guion, voz, escenas y ajustes en el estudio">
            Reutilizar
          </button>
          {playable && (
            <button
              type="button"
              className="btn btn--sm lib-download"
              aria-label={`Descargar «${item.topic}»`}
              title="Descargar el video"
              onClick={() => download(library.videoUrl(item.id))}
            >
              ↓
            </button>
          )}
          <Menu label={`Más acciones de «${item.topic}»`} items={more} />
        </div>
      )}
    </article>
  );
}
