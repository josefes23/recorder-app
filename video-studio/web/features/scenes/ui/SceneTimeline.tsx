"use client";

import type { Timeline } from "@/domain/scene";

/**
 * Reparte la duración del vídeo entre las escenas y marca dónde acaba la voz.
 * Los huecos, los tramos y las escenas muertas se ven de un vistazo, que es
 * justo lo que una lista de segundos no enseña.
 */
export function SceneTimeline({
  timeline,
  voiceSeconds,
}: {
  timeline: Timeline;
  voiceSeconds: number;
}) {
  const { segments, total } = timeline;
  const overflows = total > voiceSeconds;

  return (
    <div className="timeline-wrap">
      <div className="timeline">
        {segments.map((segment, i) => (
          <div
            key={i}
            className={`timeline-seg${segment.late ? " is-late" : ""}`}
            style={{ flexGrow: segment.span }}
            title={
              `Escena ${i + 1} · del segundo ${segment.start} al ${segment.end}` +
              ` · ${segment.span.toFixed(1)} s en pantalla` +
              (segment.repeats > 1 ? ` · el clip se repite ${segment.repeats} veces` : "")
            }
          >
            {i + 1}
          </div>
        ))}
        {overflows && (
          <div className="timeline-end" style={{ left: `${(voiceSeconds / total) * 100}%` }} />
        )}
      </div>

      {/* Cuando alguna escena se pasa del final, la barra se estira para que se
          vea el tramo muerto y su borde derecho ya no es la duración del vídeo:
          por eso esa cifra se mueve a la marca y aparece el total aparte. */}
      <div className="timeline-scale">
        <span className="num">0 s</span>
        <span
          className={overflows ? "at-mark" : undefined}
          style={overflows ? { left: `${(voiceSeconds / total) * 100}%` } : undefined}
        >
          vídeo <b className="num">{voiceSeconds.toFixed(0)}</b> s
        </span>
        {overflows && <span className="num">{total.toFixed(0)} s</span>}
      </div>
    </div>
  );
}
