"use client";

import { isPlayable, type VideoItem } from "@/domain/library";
import { useLibrary } from "@/features/library/model/use-library";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";
import { CopyButton } from "@/shared/ui/CopyButton";

function Meta({ item }: { item: VideoItem }) {
  return (
    <p className={`hint${item.status !== "done" ? ` status-${item.status}` : ""}`}>
      {isPlayable(item) ? (
        <>
          <b className="num">{item.duration ?? "?"}</b> s ·{" "}
          <b className="num">{item.size_mb ?? "?"}</b> MB ·{" "}
          <b className="num">{item.captions ?? "?"}</b> bloques
        </>
      ) : item.status === "error" ? (
        "Falló"
      ) : (
        item.status
      )}
      <br />
      {item.created_at?.replace("T", " ")}
    </p>
  );
}

export function LibraryPanel() {
  const library = useLibrary();
  const { reuse } = useStudioActions();

  return (
    <section className="panel panel--loose stack">
      <h2 className="panel-title">Biblioteca</h2>
      {library.items.length === 0 ? (
        <p className="hint">Aquí aparecerán los videos en cuanto renderices el primero.</p>
      ) : (
        <div className="library">
          {library.items.map((item) => (
            <div className="lib-item" key={item.id}>
              {isPlayable(item) && (
                <video src={library.videoUrl(item.id)} controls preload="metadata" />
              )}
              <h3>{item.topic}</h3>
              <Meta item={item} />
              {item.error && <p className="error">{item.error}</p>}
              <div className="cluster">
                {isPlayable(item) && (
                  <>
                    <a className="btn btn--sm" href={library.videoUrl(item.id)} download>
                      Descargar
                    </a>
                    <a
                      className="btn btn--sm"
                      href={library.coverUrl(item.id)}
                      download
                      title="La portada con su título, a 1080x1920"
                    >
                      Portada
                    </a>
                    {item.description?.trim() && (
                      <CopyButton text={item.description} label="Descripción" />
                    )}
                  </>
                )}
                <button className="btn btn--sm" onClick={() => reuse(item)}>
                  Reutilizar
                </button>
                <button
                  className="btn btn--sm"
                  onClick={() => {
                    if (confirm("¿Borrar este video y su archivo?")) library.remove(item.id);
                  }}
                >
                  Borrar
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
