"use client";

import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { buildTimeline, draggedStart, withStart, type Scene, type Timeline } from "@/domain/scene";
import { describeTransition, type Transition } from "@/domain/transition";

import { carriesScene, droppedScene, startSceneDrag } from "./scene-drag";

type Props = {
  scenes: Scene[];
  timeline: Timeline;
  voiceSeconds: number;
  /** Miniatura de cada escena, en el mismo orden; null si no hay. */
  thumbs: (string | null)[];
  selected: number;
  onSelect: (index: number) => void;
  /** Al soltar un borde (o moverlo con el teclado): el nuevo inicio de esa escena. */
  onMove: (index: number, start: number) => void;
  /** La del video, para las escenas que no eligen la suya. */
  fallback: Transition;
  /** Pulsaron la marca de transición de esa escena. */
  onTransition: (index: number) => void;
  /** Lo que dice la voz en cada escena, para el aviso al pasar por encima. */
  said?: string[];
  /** Soltar un tramo (o una fila de la lista) sobre otro intercambia sus imágenes. */
  onSwap: (a: number, b: number) => void;
  /** Se está eligiendo con qué escena intercambiar. */
  picking?: boolean;
};

const pct = (value: number, total: number) => `${(Math.max(0, value) / total) * 100}%`;
const secondsText = (value: number) => `${value.toLocaleString("es", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s`;

/**
 * La duración del video repartida entre las escenas, y editable: cada tramo
 * elige su escena, cada borde se arrastra para cambiar cuándo entra la
 * siguiente, y encima de cada borde una marca dice con qué transición entra
 * (◆ la suya, ◇ la del video). Arrastrar nunca desordena las escenas.
 */
export function SceneTimeline({
  scenes, timeline, voiceSeconds, thumbs, selected, onSelect, onMove, fallback, onTransition, said = [], onSwap,
  picking = false,
}: Props) {
  const bar = useRef<HTMLDivElement>(null);
  /** El borde que se está arrastrando y adónde va; se aplica al soltar. */
  const [drag, setDrag] = useState<{ index: number; start: number; total: number } | null>(null);
  /** El tramo sobre el que caería una imagen arrastrada. */
  const [target, setTarget] = useState<number | null>(null);

  // Mientras se arrastra se pinta con el inicio provisional, sin tocar el estado.
  const shown = drag ? buildTimeline(withStart(scenes, drag.index, drag.start), voiceSeconds) : timeline;
  const total = drag?.total ?? shown.total;
  const { segments } = shown;
  const overflows = total > voiceSeconds;
  const movable = !timeline.disordered;

  const startAt = (index: number) => segments[index]?.start ?? 0;

  const toSeconds = (clientX: number) => {
    const rect = bar.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return 0;
    return ((clientX - rect.left) / rect.width) * total;
  };

  const grab = (index: number) => (event: PointerEvent<HTMLDivElement>) => {
    if (!movable) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({ index, start: scenes[index].start, total: timeline.total });
  };
  const move = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag) return;
    setDrag({ ...drag, start: draggedStart(scenes, drag.index, toSeconds(event.clientX), drag.total) });
  };
  const release = () => {
    if (!drag) return;
    if (drag.start !== scenes[drag.index].start) onMove(drag.index, drag.start);
    setDrag(null);
  };
  const nudge = (index: number) => (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 1 : 0.1;
    const delta = event.key === "ArrowLeft" ? -step : event.key === "ArrowRight" ? step : 0;
    if (!delta || !movable) return;
    event.preventDefault();
    const next = draggedStart(scenes, index, scenes[index].start + delta, timeline.total);
    if (next !== scenes[index].start) onMove(index, next);
  };

  return (
    <div className="timeline-wrap">
      {/* Las marcas de transición van encima de cada borde, fuera de la barra:
          así no se pisan con el asa de arrastre. */}
      <div className="timeline-lane">
        {segments.slice(1).map((_, k) => {
          const i = k + 1;
          const own = scenes[i]?.transition;
          const used = own ?? fallback;
          return (
            <button
              key={i}
              type="button"
              className={`timeline-mark${own ? " is-own" : ""}${used.kind === "corte" ? " is-cut" : ""}`}
              style={{ left: pct(startAt(i), total) }}
              title={`Escena ${i + 1} entra con: ${describeTransition(used)}${own ? "" : " (la del video)"}`}
              aria-label={`Transición de entrada de la escena ${i + 1}: ${describeTransition(used)}`}
              onClick={() => onTransition(i)}
            >
              {own ? "◆" : "◇"}
            </button>
          );
        })}
      </div>

      <div className={`timeline${drag ? " is-dragging" : ""}`} ref={bar}>
        {segments.map((segment, i) => (
          <button
            key={i}
            type="button"
            className={
              `timeline-seg${segment.late ? " is-late" : ""}${i === selected ? " is-selected" : ""}` +
              `${target === i ? " is-drop" : ""}${picking ? " is-pick" : ""}`
            }
            draggable={!picking && !drag}
            onDragStart={(e) => startSceneDrag(e, i)}
            onDragOver={(e) => {
              if (!carriesScene(e)) return;
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
              if (target !== i) setTarget(i);
            }}
            onDragLeave={() => setTarget((t) => (t === i ? null : t))}
            onDragEnd={() => setTarget(null)}
            onDrop={(e) => {
              e.preventDefault();
              setTarget(null);
              const from = droppedScene(e);
              if (from !== null && from !== i) onSwap(from, i);
            }}
            style={{
              left: pct(segment.start, total),
              width: pct(Math.max(segment.end - segment.start, 0), total),
              backgroundImage: thumbs[i] ? `url("${thumbs[i]}")` : undefined,
            }}
            aria-pressed={i === selected}
            title={
              `Escena ${i + 1} · del segundo ${segment.start.toFixed(1)} al ${segment.end.toFixed(1)}` +
              ` · ${segment.span.toFixed(1)} s en pantalla` +
              (segment.repeats > 1 ? ` · el clip se repite ${segment.repeats} veces` : "") +
              (said[i] ? `\n«${said[i]}»` : "") +
              (picking ? `\nIntercambiar con la escena ${i + 1}` : "\nArrástralo sobre otro tramo para intercambiar las imágenes")
            }
            onClick={() => onSelect(i)}
          >
            <span className="timeline-n">{i + 1}</span>
          </button>
        ))}

        {/* Un asa por borde, desde la segunda escena: la primera empieza en 0. */}
        {movable &&
          segments.slice(1).map((_, k) => {
            const i = k + 1;
            const start = startAt(i);
            return (
              <div
                key={i}
                className={`timeline-handle${drag?.index === i ? " is-active" : ""}`}
                style={{ left: pct(start, total) }}
                role="slider"
                tabIndex={0}
                aria-label={`Inicio de la escena ${i + 1}`}
                aria-valuemin={0}
                aria-valuemax={Math.round(total * 10) / 10}
                aria-valuenow={start}
                aria-valuetext={secondsText(start)}
                title="Arrastra para cambiar cuándo entra esta escena (o usa las flechas; con mayúsculas, de segundo en segundo)"
                onPointerDown={grab(i)}
                onPointerMove={move}
                onPointerUp={release}
                onPointerCancel={() => setDrag(null)}
                onKeyDown={nudge(i)}
              >
                {drag?.index === i && <span className="timeline-tip num">{secondsText(drag.start)}</span>}
              </div>
            );
          })}

        {overflows && <div className="timeline-end" style={{ left: pct(voiceSeconds, total) }} />}
      </div>

      {/* Cuando alguna escena se pasa del final, la barra se estira para que se
          vea el tramo muerto y su borde derecho ya no es la duración del vídeo:
          por eso esa cifra se mueve a la marca y aparece el total aparte. */}
      <div className="timeline-scale">
        <span className="num">0 s</span>
        <span
          className={overflows ? "at-mark" : undefined}
          style={overflows ? { left: pct(voiceSeconds, total) } : undefined}
        >
          vídeo <b className="num">{voiceSeconds.toFixed(0)}</b> s
        </span>
        {overflows && <span className="num">{total.toFixed(0)} s</span>}
      </div>
    </div>
  );
}
