"use client";

import { useState, type ReactNode } from "react";

import {
  MAX_ATTEMPTS,
  castIn,
  correctionDraft,
  reviewNote,
  savedNamed,
  type ImageReview,
} from "@/domain/illustration";
import { clipSeconds, formatUsd } from "@/domain/animation";
import { animatable, pendingClips, pendingImages } from "@/domain/scene";
import { useAnimation } from "@/features/animation/model/use-animation";
import { AnimationControls } from "@/features/animation/ui/AnimationControls";
import { BackgroundPicker } from "@/features/backgrounds/ui/BackgroundPicker";
import { useBackgrounds } from "@/features/backgrounds/model/use-backgrounds";
import { useCharacters } from "@/features/illustrations/model/use-characters";
import { useImages } from "@/features/illustrations/model/use-images";
import { CharactersEditor } from "@/features/illustrations/ui/CharactersEditor";
import { ImageChoiceSelect } from "@/features/illustrations/ui/ImageChoiceSelect";
import { ReferenceThumb } from "@/features/illustrations/ui/ReferenceThumb";
import { SceneImageCorrector } from "@/features/illustrations/ui/SceneImageCorrector";
import { SceneImageEditor } from "@/features/illustrations/ui/SceneImageEditor";
import { UnconfiguredProviders } from "@/features/illustrations/ui/UnconfiguredProviders";
import { useScenes, useTimeline } from "@/features/scenes/model/use-scenes";
import { useScript } from "@/features/script/model/use-script";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { useWriter } from "@/features/writer/model/use-writer";
import { Field } from "@/shared/ui/Field";
import { Lightbox } from "@/shared/ui/Lightbox";
import { Step } from "@/shared/ui/Step";

import { SceneTimeline } from "./SceneTimeline";

type Props = {
  /** Panel del generador de imágenes. Lo inyecta la página, como el del guion. */
  settings?: ReactNode;
};

export function ScenesStep({ settings }: Props) {
  const scenes = useScenes();
  const backgrounds = useBackgrounds();
  const images = useImages();
  const animation = useAnimation();
  const writer = useWriter();
  const actions = useStudioActions();
  const { busy } = useStatus();
  const { seconds, text } = useScript();
  const timeline = useTimeline();

  /* undefined = cerrado · null = añadir escena · número = cambiar esa escena */
  const [target, setTarget] = useState<number | null | undefined>(undefined);
  /** Escena abierta a tamaño grande, o null. */
  const [peek, setPeek] = useState<number | null>(null);
  /** Escena con el editor de imagen abierto, «new» para una nueva, o null. */
  const [editing, setEditing] = useState<number | "new" | null>(null);
  /** Escena con el panel «Corregir» abierto, o null. Uno de los dos paneles a la vez. */
  const [correcting, setCorrecting] = useState<number | null>(null);

  const openEditor = (index: number | "new" | null) => {
    setCorrecting(null);
    setEditing(index);
  };
  const openCorrector = (index: number | null) => {
    setEditing(null);
    setCorrecting(index);
  };

  const peeked =
    peek === null
      ? undefined
      : backgrounds.items.find((b) => b.name === scenes.items[peek]?.background);

  const voice = Math.max(seconds, 1);
  const waiting = pendingImages(scenes.items);
  const animating = pendingClips(scenes.items);
  const hasScript = text.trim().length > 0;
  const usdPerSecond = animation.settings?.usdPerSecond ?? 0;

  const aiHint = !images.choice
    ? "Configura un generador en «Generador de imágenes», al final de este paso: Cloudflare es gratis."
    : !writer.label
      ? "Qué se ve en cada escena lo decide el modelo del guion: configúralo en «Modelo del guion»."
      : !hasScript
        ? "Escribe primero el guion: cada escena sale de una o dos de sus frases."
        : `${writer.label} escribe primero el guion visual —qué se ve en cada escena, quién o qué sale y con qué estilo— y después se pinta una imagen cada unos 6 s.${
            scenes.items.length
              ? " Sustituye las escenas actuales; quien siga en el reparto se mantiene si encaja, así que quita antes a quien no quieras."
              : ""
          }`;

  return (
    <Step
      n={4}
      title="Escenas"
      note={scenes.items.length ? `${scenes.items.length} sobre ${voice.toFixed(0)} s` : "fondo generado"}
    >
      <div className="ai-panel">
        <Field id="images-look" label="Estilo visual, común a todas las escenas">
          <textarea
            id="images-look"
            rows={2}
            value={images.guide.look}
            onChange={(e) => images.setLook(e.target.value)}
            placeholder="fotografía cinematográfica, ilustración plana, acuarela…"
          />
        </Field>
        <CharactersEditor />
        {images.choice && (
          <Field id="images-choice" label="Pintar con">
            <ImageChoiceSelect id="images-choice" />
          </Field>
        )}
        <UnconfiguredProviders />
        {writer.seesImages ? (
          <label className="cluster check" htmlFor="images-review">
            <input
              id="images-review"
              type="checkbox"
              checked={images.review}
              onChange={(e) => images.setReview(e.target.checked)}
            />
            <span className="hint">
              Revisar cada imagen con {writer.label}: si ve manos o brazos de más, cuerpos fundidos
              o letras, la repinta con otra semilla (hasta {MAX_ATTEMPTS} intentos).
            </span>
          </label>
        ) : (
          writer.label && (
            <p className="hint">
              {writer.label} no ve imágenes, así que no las revisa. Para que se repinten las que
              salgan con manos de más o letras, elige Claude o Gemini en «Modelo del guion».
            </p>
          )
        )}
        <button
          className="btn btn--primary btn--block"
          disabled={!images.choice || !writer.label || !hasScript || busy !== null}
          onClick={actions.illustrateAll}
        >
          {busy === "storyboard"
            ? "Escribiendo el guion visual…"
            : busy === "illustrate"
              ? "Pidiendo imágenes…"
              : scenes.items.length
                ? "Rehacer las escenas desde el guion"
                : "Generar escenas desde el guion"}
        </button>
        <p className="hint">{aiHint}</p>
        <AnimationControls />
      </div>

      {scenes.items.length === 0 ? (
        <p className="hint">
          Sin escenas se usa el fondo animado que genera el motor. Genéralas desde el guion o
          añade una a mano.
        </p>
      ) : (
        <>
          <SceneTimeline timeline={timeline} voiceSeconds={voice} />

          {waiting > 0 && (
            <p className="hint">
              {waiting === 1 ? "Llega 1 imagen" : `Llegan ${waiting} imágenes`}. Puedes seguir
              ajustando mientras tanto; si renderizas antes, esas escenas no saldrán.
            </p>
          )}
          {animating > 0 && (
            <p className="hint">
              {animating === 1 ? "Se está animando 1 escena" : `Se están animando ${animating} escenas`}:
              cada clip tarda unos minutos. Si renderizas antes, salen con su imagen fija.
            </p>
          )}
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
              const source = animatable(scene);
              const seconds = clipSeconds(segment.span);
              return (
                <div className="scene-item" key={`${scene.job ?? scene.background}-${i}`}>
                  <div className="scene-row">
                    {scene.job || scene.clipJob ? (
                      <div
                        className="scene-thumb scene-thumb--busy"
                        title={scene.job ? "Generando la imagen…" : "Animando la imagen…"}
                      />
                    ) : meta?.thumb ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        className="scene-thumb"
                        src={backgrounds.thumbUrl(meta.thumb)}
                        alt=""
                        title="Cambiar por un clip de Pexels o de la galería"
                        onClick={() => setTarget(i)}
                      />
                    ) : (
                      <button
                        className="scene-thumb scene-thumb--empty"
                        title="Elegir un clip de Pexels o de la galería"
                        aria-label={`Elegir un fondo para la escena ${i + 1}`}
                        onClick={() => setTarget(i)}
                      >
                        +
                      </button>
                    )}
                    <div className="scene-name">
                      <span>
                        {scene.background ??
                          (scene.job ? "Generando imagen…" : scene.prompt ? "Sin imagen" : "(fondo generado)")}
                      </span>
                      {scene.prompt && <span className="hint scene-prompt">«{scene.prompt}»</span>}
                      {scene.prompt && <SceneCast description={scene.prompt} />}
                      <span className="hint">
                        del <b className="num">{segment.start.toFixed(0)}</b> al{" "}
                        <b className="num">{segment.end.toFixed(0)}</b> s ·{" "}
                        <b className="num">{segment.span.toFixed(1)}</b> s en pantalla
                      </span>
                      {scene.error && <span className="hint warn">{scene.error}</span>}
                      {scene.review && <ReviewNote review={scene.review} />}
                      {scene.clipJob && (
                        <span className="hint">
                          Animando un clip de <b className="num">{seconds}</b> s: tarda unos minutos.
                        </span>
                      )}
                      {scene.still && !scene.clipJob && (
                        <span className="hint">Animada desde {scene.still}</span>
                      )}
                      {scene.clipError && <span className="hint warn">{scene.clipError}</span>}
                      {segment.repeats > 1 && (
                        <span className="hint warn">
                          El clip dura <b className="num">{meta?.duration}</b> s: se repetirá{" "}
                          <b className="num">{segment.repeats}</b> veces para cubrir el tramo.
                        </span>
                      )}
                    </div>
                    {meta && (
                      <button
                        className="btn btn--sm"
                        title="Ver el fondo a tamaño grande"
                        onClick={() => setPeek(i)}
                      >
                        Ver
                      </button>
                    )}
                    <button
                      className="btn btn--sm"
                      title="Generar una imagen nueva para esta escena"
                      disabled={Boolean(scene.job || scene.clipJob)}
                      onClick={() => openEditor(editing === i ? null : i)}
                    >
                      IA
                    </button>
                    {meta?.kind === "image" && (
                      <button
                        className="btn btn--sm"
                        title="Decirle a la IA qué está mal en esta imagen para que lo arregle"
                        disabled={Boolean(scene.job || scene.clipJob)}
                        aria-expanded={correcting === i}
                        onClick={() => openCorrector(correcting === i ? null : i)}
                      >
                        Corregir
                      </button>
                    )}
                    {animation.ready && (source || scene.clipJob) && (
                      <button
                        className="btn btn--sm"
                        title={`Convertir la imagen en un clip de ${seconds} s (≈ ${formatUsd(seconds * usdPerSecond)})`}
                        disabled={!source}
                        onClick={() => actions.animateScene(i)}
                      >
                        {scene.still ? "Reanimar" : "Animar"}
                      </button>
                    )}
                    {scene.still && !scene.clipJob && (
                      <button
                        className="btn btn--sm"
                        title={`Volver a la imagen fija (${scene.still}). El clip se queda en la galería.`}
                        onClick={() => scenes.restoreStill(i)}
                      >
                        Imagen fija
                      </button>
                    )}
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
                      onClick={() => {
                        openEditor(null); // los índices se mueven al quitar una
                        scenes.remove(i);
                      }}
                    >
                      ×
                    </button>
                  </div>

                  {editing === i && (
                    <SceneImageEditor
                      index={i}
                      initial={scene.prompt ?? ""}
                      onDone={() => setEditing(null)}
                    />
                  )}
                  {correcting === i && meta?.kind === "image" && !scene.job && (
                    <SceneImageCorrector
                      index={i}
                      initial={correctionDraft(scene.review)}
                      onDone={() => setCorrecting(null)}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      <div className="scene-add">
        <button className="btn" onClick={() => setTarget(null)}>
          Añadir de Pexels o la galería
        </button>
        <button className="btn" disabled={editing === "new"} onClick={() => openEditor("new")}>
          Añadir con IA
        </button>
      </div>
      {editing === "new" && (
        <SceneImageEditor index={null} initial="" onDone={() => setEditing(null)} />
      )}

      {settings}

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

      {peek !== null && peeked && (
        <Lightbox
          id={`scene-${peek}-${peeked.name}`}
          media={{
            kind: peeked.kind,
            src: backgrounds.fileUrl(peeked.name),
            poster: backgrounds.thumbUrl(peeked.thumb),
          }}
          info={
            <>
              <strong>Escena {peek + 1}</strong> · {peeked.name}
              {peeked.duration ? ` · ${peeked.duration}s` : ""}
            </>
          }
          actions={
            <>
              <button
                className="btn"
                onClick={() => {
                  setPeek(null);
                  setTarget(peek);
                }}
              >
                Cambiar por Pexels o galería
              </button>
              <button
                className="btn"
                onClick={() => {
                  setPeek(null);
                  openEditor(peek);
                }}
              >
                Generar otra con IA
              </button>
              {peeked.kind === "image" && !scenes.items[peek]?.job && (
                <button
                  className="btn"
                  onClick={() => {
                    setPeek(null);
                    openCorrector(peek);
                  }}
                >
                  Corregir esta imagen
                </button>
              )}
            </>
          }
          onClose={() => setPeek(null)}
        />
      )}
    </Step>
  );
}

function ReviewNote({ review }: { review: ImageReview }) {
  const note = reviewNote(review);
  return <span className={note.warn ? "hint warn" : "hint"}>{note.text}</span>;
}

/** Quién o qué del reparto sale en la escena, con su referencia si está guardado. */
function SceneCast({ description }: { description: string }) {
  const images = useImages();
  const library = useCharacters();
  const named = castIn(description, images.guide.characters);
  if (named.length === 0) return null;
  return (
    <span className="cluster scene-cast">
      {named.map((character) => (
        <span className="hint scene-cast-item" key={character.name}>
          <ReferenceThumb saved={character.saved ? savedNamed(library.items, character.name) : undefined} mini />
          {character.name}
        </span>
      ))}
    </span>
  );
}

