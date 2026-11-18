"use client";

import { useState } from "react";

import { sceneState, type Scene, type SceneState, type Timeline } from "@/domain/scene";
import type { SceneNarration } from "@/features/scenes/model/use-scenes";
import { transitionLabel } from "@/domain/transition";

import { carriesScene, droppedScene, insertionTarget, startSceneDrag, zoneOf, type DropZone } from "./scene-drag";

type Props = {
  scenes: Scene[];
  timeline: Timeline;
  thumbs: (string | null)[];
  selected: number;
  onSelect: (index: number) => void;
  checked: ReadonlySet<number>;
  onCheck: (index: number, on: boolean) => void;
  onCheckAll: (on: boolean) => void;
  /** Lo que dice la voz en cada escena y cuándo. */
  narration: SceneNarration[];
  /** Lleva la imagen de una escena a otra, corriendo las de en medio. */
  onMove: (from: number, to: number) => void;
  /** Intercambia las imágenes de dos escenas. */
  onSwap: (a: number, b: number) => void;
  /** Se está eligiendo con qué escena intercambiar: cada fila es un destino. */
  picking?: boolean;
};

const STATE_LABEL: Record<SceneState, string | null> = {
  painting: "Pintando…",
  animating: "Animando…",
  failed: "Falló",
  review: "Revisar",
  empty: "Sin imagen",
  ready: null,
};

/**
 * Una línea por escena: lo justo para reconocerla y ver si pide atención. Lo
 * que se hace con ella está en el inspector, a un clic.
 */
export function SceneList({
  scenes, timeline, thumbs, selected, onSelect, checked, onCheck, onCheckAll, narration, onMove, onSwap, picking = false,
}: Props) {
  const all = scenes.length > 0 && checked.size === scenes.length;
  /** La fila que se arrastra y dónde caería: antes, después o encima (intercambiar). */
  const [dragging, setDragging] = useState<number | null>(null);
  const [drop, setDrop] = useState<{ index: number; zone: DropZone } | null>(null);
  const endDrag = () => {
    setDragging(null);
    setDrop(null);
  };
  return (
    <div className="scene-list">
      <label className="cluster check scene-list-head" htmlFor="scenes-check-all">
        <input
          id="scenes-check-all"
          type="checkbox"
          checked={all}
          ref={(el) => {
            if (el) el.indeterminate = checked.size > 0 && !all;
          }}
          onChange={(e) => onCheckAll(e.target.checked)}
        />
        <span className="hint">{checked.size ? `${checked.size} marcadas` : "Marcar todas"}</span>
      </label>
      <ol className="scene-lines">
        {scenes.map((scene, i) => {
          const segment = timeline.segments[i];
          const said = narration[i];
          const state = sceneState(scene);
          const label = STATE_LABEL[state];
          const busy = state === "painting" || state === "animating";
          return (
            <li
              key={`${scene.job ?? scene.background}-${i}`}
              className={
                `scene-line${i === selected ? " is-selected" : ""}${dragging === i ? " is-dragging" : ""}` +
                `${drop?.index === i ? ` is-drop-${drop.zone}` : ""}${picking ? " is-pick" : ""}`
              }
              draggable={!picking}
              onDragStart={(e) => {
                startSceneDrag(e, i);
                setDragging(i);
              }}
              onDragEnd={endDrag}
              onDragOver={(e) => {
                if (!carriesScene(e)) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                const zone = zoneOf(e);
                if (drop?.index !== i || drop.zone !== zone) setDrop({ index: i, zone });
              }}
              onDragLeave={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node)) setDrop((d) => (d?.index === i ? null : d));
              }}
              onDrop={(e) => {
                e.preventDefault();
                const from = droppedScene(e);
                const zone = zoneOf(e);
                endDrag();
                if (from === null || from === i) return;
                if (zone === "swap") onSwap(from, i);
                else {
                  const to = insertionTarget(from, i, zone);
                  if (to !== from) onMove(from, to);
                }
              }}
            >
              <span className="scene-grip" aria-hidden="true" title="Arrastra para mover la imagen">
                ⠿
              </span>
              <input
                type="checkbox"
                checked={checked.has(i)}
                aria-label={`Marcar la escena ${i + 1}`}
                onChange={(e) => onCheck(i, e.target.checked)}
              />
              <button
                type="button"
                className="scene-line-main"
                aria-current={i === selected ? "true" : undefined}
                title={
                  picking
                    ? `Intercambiar con la escena ${i + 1}`
                    : "Arrastra para mover la imagen; suéltala en el centro de otra para intercambiarlas. Con el teclado: Alt+↑ / Alt+↓"
                }
                onClick={() => onSelect(i)}
                onKeyDown={(e) => {
                  if (!e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
                  const to = e.key === "ArrowUp" ? i - 1 : i + 1;
                  if (to < 0 || to >= scenes.length) return;
                  e.preventDefault();
                  onMove(i, to);
                }}
              >
                {busy ? (
                  <span className="scene-line-thumb scene-thumb--busy" />
                ) : thumbs[i] ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img className="scene-line-thumb" src={thumbs[i] ?? ""} alt="" />
                ) : (
                  <span className="scene-line-thumb scene-thumb--empty" />
                )}
                <span className="scene-line-n num">{i + 1}</span>
                <span className="scene-line-text" title={scene.prompt || scene.background || undefined}>
                  {/* Lo que se oye mientras se ve: con eso se elige la imagen */}
                  <span className="scene-line-name">
                    {said?.text ? `«${said.text}»` : scene.prompt || scene.background || "(fondo generado)"}
                  </span>
                  <span className="hint num">
                    {(said?.start ?? segment.start).toFixed(1)}–{(said?.end ?? segment.end).toFixed(1)} s
                  </span>
                </span>
                <span className="scene-line-tags">
                  {scene.transition && <span className="tag">◆ {transitionLabel(scene.transition.kind)}</span>}
                  {scene.still && !scene.clipJob && <span className="tag">Animada</span>}
                  {segment.late && <span className="tag is-warn">No se ve</span>}
                  {label && <span className={`tag${busy ? " is-busy" : " is-warn"}`}>{label}</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
