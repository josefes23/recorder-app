"use client";

import { useState } from "react";

import { coverFilename } from "@/domain/cover";
import { canRender } from "@/domain/script";
import { voiceLabel } from "@/domain/voice";
import { useCover } from "@/features/cover/model/use-cover";
import { CoverControls } from "@/features/cover/ui/CoverControls";
import { useDescription } from "@/features/description/model/use-description";
import { useLibrary } from "@/features/library/model/use-library";
import { useProduction } from "@/features/production/model/use-production";
import { useRender } from "@/features/render/model/use-render";
import { useScenes } from "@/features/scenes/model/use-scenes";
import { useScript } from "@/features/script/model/use-script";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { useVoice, useVoiceCatalog } from "@/features/voice/model/use-voice";
import { CopyButton } from "@/shared/ui/CopyButton";

type View = "cover" | "frame";

export function OutputPanel() {
  const render = useRender();
  const cover = useCover();
  const description = useDescription();
  const library = useLibrary();
  const script = useScript();
  const scenes = useScenes();
  const voice = useVoice();
  const catalog = useVoiceCatalog();
  const { format } = useProduction();
  /* El cuadro toma la forma del video: vertical o apaisado. */
  const shape = format === "16:9" ? " frame--wide" : "";
  const { busy, error } = useStatus();
  const actions = useStudioActions();

  // La portada primero: es lo que decide si alguien abre el video.
  const [view, setView] = useState<View>("cover");

  const progress = Math.max(2, (render.job?.progress ?? 0) * 100);
  const ready = canRender(script.text);
  const done = render.job?.status === "done" ? render.job : null;

  return (
    <div className="panel panel--pad stack">
      <h2 className="panel-title">Salida</h2>

      <div className="tabs" role="tablist" aria-label="Qué previsualizar">
        <button
          role="tab"
          aria-selected={view === "cover"}
          className={`tab${view === "cover" ? " is-on" : ""}`}
          onClick={() => setView("cover")}
        >
          Portada
        </button>
        <button
          role="tab"
          aria-selected={view === "frame"}
          className={`tab${view === "frame" ? " is-on" : ""}`}
          onClick={() => setView("frame")}
        >
          Fotograma
        </button>
      </div>

      {view === "cover" ? (
        <div className={`frame${shape}${cover.painting ? " is-busy" : ""}`} aria-busy={cover.painting}>
          {cover.imageUrl ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img src={cover.imageUrl} alt="Portada del video" />
          ) : (
            <p className="frame-empty">
              {cover.painting
                ? "Pintando la portada…"
                : "Escribe el tema del video en el paso 1, o un título aquí abajo, para ver la portada."}
            </p>
          )}
        </div>
      ) : (
        <div className={`frame${shape}`}>
          {render.previewUrl ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img src={render.previewUrl} alt="Fotograma de previsualización" />
          ) : (
            <p className="frame-empty">
              Previsualiza un fotograma para ver cómo quedan los subtítulos sobre el fondo.
            </p>
          )}
        </div>
      )}

      {view === "cover" ? (
        <>
          {cover.failure && <p className="error">{cover.failure}</p>}
          <CoverControls />
        </>
      ) : (
        <button className="btn btn--block" disabled={busy !== null} onClick={actions.preview}>
          {busy === "preview" ? "Generando…" : "Previsualizar fotograma"}
        </button>
      )}

      {/* Qué va a salir de aquí, sin tener que releer los pasos */}
      <dl className="readout">
        <div className="readout-row">
          <dt>Duración</dt>
          <dd className={script.verdict === "short" || script.verdict === "long" ? "hint warn" : ""}>
            <b className="num">{script.seconds.toFixed(0)}</b> s
          </dd>
        </div>
        <div className="readout-row">
          <dt>Voz</dt>
          <dd>{voiceLabel(catalog, voice.id) ?? "…"}</dd>
        </div>
        <div className="readout-row">
          <dt>Escenas</dt>
          <dd>
            {scenes.items.length ? <b className="num">{scenes.items.length}</b> : "fondo generado"}
          </dd>
        </div>
      </dl>

      <button
        className="btn btn--primary btn--block btn--lg"
        disabled={!ready || render.rendering || busy !== null}
        onClick={actions.render}
      >
        {render.rendering ? "Renderizando…" : "Renderizar video"}
      </button>

      {!ready && <p className="hint">Escribe el guion del paso 1 para poder renderizar.</p>}

      {render.job && render.job.status !== "error" && (
        <div className="stack">
          <div className="progress">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <p className="hint">{render.job.message ?? render.job.status}</p>
        </div>
      )}

      {done && (
        <div className="done">
          <p className="done-title">Video listo</p>
          <div className="cluster">
            <a className="btn btn--sm btn--primary" href={library.videoUrl(done.id)} download>
              Descargar video
            </a>
            {/* La que se ve ahora, aunque se haya retocado después del render; si
                aún no hay ninguna pintada, la guardada con el video. */}
            <a
              className="btn btn--sm"
              href={cover.imageUrl ?? library.coverUrl(done.id)}
              download={cover.imageUrl ? coverFilename(script.topic) : true}
            >
              Descargar portada
            </a>
            {description.text.trim() && (
              <CopyButton text={description.text} label="Copiar descripción" />
            )}
          </div>
          <p className="hint">
            La portada sale a 1080x1920 con el título dentro del recorte 3:4 de la cuadrícula: lista
            para subirla como portada del Reel, el TikTok o el Short.
          </p>
        </div>
      )}

      {error && <p className="error">{error}</p>}
    </div>
  );
}
