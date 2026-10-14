"use client";

import { useState } from "react";

import { BackgroundPicker } from "@/features/backgrounds/ui/BackgroundPicker";
import { useBackgrounds } from "@/features/backgrounds/model/use-backgrounds";
import { useScenes, useTimeline } from "@/features/scenes/model/use-scenes";
import { useScript } from "@/features/script/model/use-script";
import { Step } from "@/shared/ui/Step";

import { SceneTimeline } from "./SceneTimeline";

export function ScenesStep() {
  const scenes = useScenes();
  const backgrounds = useBackgrounds();
  const { seconds } = useScript();
  const timeline = useTimeline();

  /* undefined = cerrado · null = añadir escena · número = cambiar esa escena */
  const [target, setTarget] = useState<number | null | undefined>(undefined);

  const voice = Math.max(seconds, 1);

  return (
    <Step
      n={4}
      title="Escenas"
      note={scenes.items.length ? `${scenes.items.length} sobre ${voice.toFixed(0)} s` : "fondo generado"}
    >
      {scenes.items.length === 0 ? (
        <p className="hint">
          Sin escenas se usa el fondo animado que genera el motor. Añade una para poner tus
          propios clips.
        </p>
      ) : (
        <>
          <SceneTimeline timeline={timeline} voiceSeconds={voice} />

          {timeline.late.length > 0 && (
            <p className="hint warn">
              La voz acaba en {voice.toFixed(0)} s, así que{" "}
              {timeline.late.length === 1
                ? `la escena ${timeline.late[0]} entra después y no se verá.`
                : `las escenas ${timeline.late.join(", ")} entran después y no se verán.`}
            </p>
          )}
          {timeline.disordered && (
            <p className="hint warn">
              Los segundos no van de menor a mayor. Ordénalos para que cada escena dure algo.
            </p>
          )}

          <div className="stack">
            {scenes.items.map((scene, i) => {
              const meta = backgrounds.items.find((b) => b.name === scene.background);
              const segment = timeline.segments[i];
              return (
                <div className="scene-row" key={`${scene.background}-${i}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    className="scene-thumb"
                    src={backgrounds.thumbUrl(meta?.thumb ?? null)}
                    alt=""
                    title="Cambiar el fondo de esta escena"
                    onClick={() => setTarget(i)}
                  />
                  <div className="scene-name">
                    <span>{scene.background ?? "(fondo generado)"}</span>
                    <span className="hint">
                      del <b className="num">{segment.start.toFixed(0)}</b> al{" "}
                      <b className="num">{segment.end.toFixed(0)}</b> s ·{" "}
                      <b className="num">{segment.span.toFixed(1)}</b> s en pantalla
                    </span>
                    {segment.repeats > 1 && (
                      <span className="hint warn">
                        El clip dura <b className="num">{meta?.duration}</b> s: se repetirá{" "}
                        <b className="num">{segment.repeats}</b> veces para cubrir el tramo.
                      </span>
                    )}
                  </div>
                  <div className="scene-start">
                    <input
                      type="number"
                      className="num"
                      min={0}
                      step={0.1}
                      value={i === 0 ? 0 : scene.start}
                      disabled={i === 0}
                      title={i === 0 ? "La primera escena empieza en 0" : "Segundo de entrada"}
                      aria-label={`Segundo de entrada de la escena ${i + 1}`}
                      onChange={(e) => scenes.setStart(i, parseFloat(e.target.value) || 0)}
                    />
                  </div>
                  <button
                    className="btn btn--icon"
                    title={`Quitar la escena ${i + 1}`}
                    onClick={() => scenes.remove(i)}
                  >
                    ×
                  </button>
                </div>
              );
            })}
          </div>
        </>
      )}

      <button className="btn btn--block" onClick={() => setTarget(null)}>
        Añadir escena
      </button>

      {/* El diálogo solo elige un fondo; qué hacer con él lo decide esta feature */}
      {target !== undefined && (
        <BackgroundPicker
          onSelect={(name) => {
            scenes.place(name, target);
            setTarget(undefined);
          }}
          onClose={() => setTarget(undefined)}
        />
      )}
    </Step>
  );
}
