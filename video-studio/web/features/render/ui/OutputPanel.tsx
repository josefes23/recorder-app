"use client";

import { canRender } from "@/domain/script";
import { voiceLabel } from "@/domain/voice";
import { useRender } from "@/features/render/model/use-render";
import { useScenes } from "@/features/scenes/model/use-scenes";
import { useScript } from "@/features/script/model/use-script";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { useVoice, useVoiceCatalog } from "@/features/voice/model/use-voice";

export function OutputPanel() {
  const render = useRender();
  const script = useScript();
  const scenes = useScenes();
  const voice = useVoice();
  const catalog = useVoiceCatalog();
  const { busy, error } = useStatus();
  const actions = useStudioActions();

  const progress = Math.max(2, (render.job?.progress ?? 0) * 100);
  const ready = canRender(script.text);

  return (
    <div className="panel panel--pad stack">
      <h2 className="panel-title">Salida</h2>

      <div className="frame">
        {render.previewUrl ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img src={render.previewUrl} alt="Fotograma de previsualización" />
        ) : (
          <p className="frame-empty">
            Previsualiza un fotograma para ver cómo quedan los subtítulos sobre el fondo.
          </p>
        )}
      </div>

      <button className="btn btn--block" disabled={busy !== null} onClick={actions.preview}>
        {busy === "preview" ? "Generando…" : "Previsualizar fotograma"}
      </button>

      {/* Qué va a salir de aquí, sin tener que releer los cuatro pasos */}
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

      {error && <p className="error">{error}</p>}
    </div>
  );
}
