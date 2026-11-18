"use client";

import { useState, type Ref } from "react";

import { MOTION_LIMIT, clipSeconds, formatUsd } from "@/domain/animation";
import { castIn, correctionDraft, reviewNote, savedNamed, type ImageReview } from "@/domain/illustration";
import { movableWords, startForWord } from "@/domain/narration";
import { animatable, takesMotion, type Scene, type TimelineSegment } from "@/domain/scene";
import { useAnimation } from "@/features/animation/model/use-animation";
import { useCharacters } from "@/features/illustrations/model/use-characters";
import { useImages } from "@/features/illustrations/model/use-images";
import { ReferenceThumb } from "@/features/illustrations/ui/ReferenceThumb";
import { SceneImageCorrector } from "@/features/illustrations/ui/SceneImageCorrector";
import { SceneImageEditor } from "@/features/illustrations/ui/SceneImageEditor";
import { useProduction } from "@/features/production/model/use-production";
import { useNarration, useSceneMedia, useScenes } from "@/features/scenes/model/use-scenes";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";
import { Menu } from "@/shared/ui/Menu";

import { TransitionPreview } from "./TransitionPreview";
import { SceneTransition } from "./TransitionPicker";

type Props = {
  index: number;
  segment: TimelineSegment;
  /** La escena de antes, para la vista previa de cómo entra esta. */
  previous: Scene | null;
  onSelect: (index: number) => void;
  /** Elegir otro fondo de Pexels o de la galería para esta escena. */
  onPick: () => void;
  /** Verla a tamaño grande. */
  onPeek: () => void;
  /** Para llevar la vista hasta aquí al elegir una escena en una pantalla estrecha. */
  ref?: Ref<HTMLElement>;
  /** Lleva la imagen de esta escena a otra (la anterior o la siguiente). */
  onMoveImage: (from: number, to: number) => void;
  /** Se está eligiendo con qué escena intercambiar la imagen de esta. */
  swapping: boolean;
  onStartSwap: () => void;
};

/** Id del selector de transición del inspector: la marca de la barra lleva el foco aquí. */
export const INSPECTOR_TRANSITION_ID = "inspector-transition";

/**
 * Todo lo que se hace con la escena elegida, en un solo sitio: verla,
 * cambiarle la imagen, corregirla, animarla, cuándo entra y cómo. Las
 * acciones que se usan poco van en «⋯».
 */
export function SceneInspector({
  index, segment, previous, onSelect, onPick, onPeek, ref, onMoveImage, swapping, onStartSwap,
}: Props) {
  const scenes = useScenes();
  const media = useSceneMedia();
  const animation = useAnimation();
  const actions = useStudioActions();
  const production = useProduction();
  const narration = useNarration();
  const scene = scenes.items[index];
  const count = scenes.items.length;
  /* Qué panel de imagen está abierto. Va con la escena: al cambiar de escena se cierra. */
  const [panel, setPanel] = useState<{ index: number; kind: "editor" | "corrector" } | null>(null);
  const open = panel?.index === index ? panel.kind : null;

  if (!scene) return null;
  const { meta, thumb, full } = media(scene.background);
  const busy = Boolean(scene.job || scene.clipJob);
  const source = animatable(scene);
  const clip = clipSeconds(segment.span);
  const usdPerSecond = animation.settings?.usdPerSecond ?? 0;
  const own = scene.transition;
  const fallback = production.transition;
  const wide = production.format === "16:9";
  const isImage = !scene.background || meta?.kind === "image";
  const said = narration.scenes[index];
  const range = movableWords(narration.scenes, index, narration.tokens.length);
  const first = said?.from ?? 0;
  const moveTo = (word: number) => scenes.setStart(index, startForWord(word));

  return (
    <section className="inspector" ref={ref} aria-label={`Escena ${index + 1}`}>
      <div className="spread inspector-head">
        <div className="cluster">
          <button
            type="button"
            className="btn btn--sm"
            disabled={index === 0}
            aria-label="Escena anterior"
            onClick={() => onSelect(index - 1)}
          >
            ‹
          </button>
          <h3 className="inspector-title">
            Escena <span className="num">{index + 1}</span> <span className="hint">de {count}</span>
          </h3>
          <button
            type="button"
            className="btn btn--sm"
            disabled={index >= count - 1}
            aria-label="Escena siguiente"
            onClick={() => onSelect(index + 1)}
          >
            ›
          </button>
        </div>
        <Menu
          label={`Más acciones de la escena ${index + 1}`}
          items={[
            { label: "Cambiar por Pexels o la galería", onSelect: onPick },
            { label: "Ver a tamaño grande", onSelect: onPeek, disabled: !meta },
            {
              label: "Quitar la escena",
              danger: true,
              onSelect: () => {
                setPanel(null);
                scenes.remove(index);
                onSelect(Math.max(0, index - 1));
              },
            },
          ]}
        />
      </div>

      <div className="inspector-body">
        {busy ? (
          <div
            className={`inspector-media scene-thumb--busy${wide ? " is-wide" : ""}`}
            title={scene.job ? "Generando la imagen…" : "Animando la imagen…"}
          />
        ) : full ? (
          <button type="button" className={`inspector-media${wide ? " is-wide" : ""}`} onClick={onPeek} title="Ver a tamaño grande">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={full} alt={scene.prompt ?? scene.background ?? ""} />
          </button>
        ) : (
          <button type="button" className={`inspector-media scene-thumb--empty${wide ? " is-wide" : ""}`} onClick={onPick}>
            Elegir un fondo
          </button>
        )}

        <div className="stack inspector-info">
          <p className="inspector-name">
            {scene.background ?? (scene.job ? "Generando imagen…" : scene.prompt ? "Sin imagen" : "(fondo generado)")}
          </p>
          {scene.prompt && <p className="hint scene-prompt">«{scene.prompt}»</p>}
          {scene.prompt && <SceneCast description={scene.prompt} />}
          <p className="hint">
            del <b className="num">{(said?.start ?? segment.start).toFixed(1)}</b> al{" "}
            <b className="num">{(said?.end ?? segment.end).toFixed(1)}</b> s ·{" "}
            <b className="num">{((said?.end ?? segment.end) - (said?.start ?? segment.start)).toFixed(1)}</b> s en
            pantalla{narration.real ? ", con la voz" : ", estimado"}
          </p>
          {scene.error && <p className="hint warn">{scene.error}</p>}
          {scene.review && <ReviewNote review={scene.review} />}
          {scene.clipJob && (
            <p className="hint">
              Animando un clip de <b className="num">{clip}</b> s: tarda unos minutos.
            </p>
          )}
          {scene.still && !scene.clipJob && <p className="hint">Animada desde {scene.still}</p>}
          {scene.clipError && <p className="hint warn">{scene.clipError}</p>}
          {segment.repeats > 1 && (
            <p className="hint warn">
              El clip dura <b className="num">{meta?.duration}</b> s: se repetirá{" "}
              <b className="num">{segment.repeats}</b> veces para cubrir el tramo.
            </p>
          )}
        </div>
      </div>

      {/* Mover la imagen sin arrastrar: con teclado o en una pantalla táctil */}
      <div className="cluster inspector-order">
        <span className="hint">Imagen</span>
        <button
          type="button"
          className="btn btn--sm"
          disabled={index === 0}
          title="Pasar esta imagen a la escena anterior (las dos se intercambian)"
          onClick={() => onMoveImage(index, index - 1)}
        >
          ‹ Antes
        </button>
        <button
          type="button"
          className="btn btn--sm"
          disabled={index >= count - 1}
          title="Pasar esta imagen a la escena siguiente (las dos se intercambian)"
          onClick={() => onMoveImage(index, index + 1)}
        >
          Después ›
        </button>
        <button
          type="button"
          className={`btn btn--sm${swapping ? " is-armed" : ""}`}
          aria-pressed={swapping}
          disabled={count < 2}
          title="Elegir otra escena en la lista o en la barra para intercambiar las imágenes"
          onClick={onStartSwap}
        >
          {swapping ? "Eligiendo… (Esc cancela)" : "Intercambiar con…"}
        </button>
      </div>

      {/* Lo que se oye mientras se ve: con esto se elige la imagen que encaja */}
      <div className="said">
        <div className="spread">
          <span className="field-label">Lo que dice la voz mientras se ve</span>
          <span className="hint">{narration.real ? "tiempos de la voz" : "tiempos estimados"}</span>
        </div>
        <blockquote className="said-text">
          {said?.text ? `«${said.text}»` : "Entra después de que acabe la voz: no se verá."}
        </blockquote>
        {range && (
          <div className="cluster said-move">
            <span className="hint">Empieza con</span>
            <button
              type="button"
              className="btn btn--sm"
              disabled={first <= range[0]}
              aria-label="Empezar una palabra antes"
              title="Que entre una palabra antes"
              onClick={() => moveTo(first - 1)}
            >
              ‹
            </button>
            <b className="said-word">«{narration.tokens[first] ?? ""}»</b>
            <button
              type="button"
              className="btn btn--sm"
              disabled={first >= range[1]}
              aria-label="Empezar una palabra después"
              title="Que entre una palabra después"
              onClick={() => moveTo(first + 1)}
            >
              ›
            </button>
          </div>
        )}
      </div>

      <div className="inspector-fields">
        <div className="field inspector-start">
          <label htmlFor="inspector-start">Segundo estimado</label>
          <input
            id="inspector-start"
            type="number"
            className="num"
            min={0}
            step={0.1}
            value={index === 0 ? 0 : scene.start}
            disabled={index === 0}
            title={index === 0 ? "La primera escena empieza en 0" : "También se cambia arrastrando su borde en la barra"}
            onChange={(e) => scenes.setStart(index, parseFloat(e.target.value) || 0)}
          />
        </div>
        {(index > 0 || isImage) && (
          <div className="inspector-transition">
            <TransitionPreview
              from={index === 0 ? thumb : previous ? media(previous.background).thumb : null}
              to={thumb}
              transition={own ?? fallback}
              wide={wide}
              reframe={index === 0}
            />
            <SceneTransition index={index} transition={own} fallback={fallback} id={INSPECTOR_TRANSITION_ID} />
          </div>
        )}
        {animation.ready && takesMotion(scene) && (
          <div className="field inspector-motion">
            <label htmlFor="inspector-motion">Movimiento al animar</label>
            <input
              id="inspector-motion"
              type="text"
              maxLength={MOTION_LIMIT}
              value={scene.motion ?? ""}
              placeholder="sutil, con la cámara despacio"
              title="Qué se mueve y qué hace la cámara al animar esta escena. Vacío: un movimiento sutil."
              onChange={(e) => scenes.setMotion(index, e.target.value)}
            />
          </div>
        )}
      </div>

      <div className="cluster">
        <button
          type="button"
          className="btn btn--sm"
          title="Generar una imagen nueva para esta escena"
          disabled={busy}
          aria-expanded={open === "editor"}
          onClick={() => setPanel(open === "editor" ? null : { index, kind: "editor" })}
        >
          Generar con IA
        </button>
        {meta?.kind === "image" && (
          <button
            type="button"
            className="btn btn--sm"
            title="Decirle a la IA qué está mal en esta imagen para que lo arregle"
            disabled={busy}
            aria-expanded={open === "corrector"}
            onClick={() => setPanel(open === "corrector" ? null : { index, kind: "corrector" })}
          >
            Corregir
          </button>
        )}
        {animation.ready && (source || scene.clipJob) && (
          <button
            type="button"
            className="btn btn--sm"
            title={`Convertir la imagen en un clip de ${clip} s`}
            disabled={!source}
            onClick={() => actions.animateScene(index)}
          >
            {scene.still ? "Reanimar" : "Animar"} · ≈ {formatUsd(clip * usdPerSecond)}
          </button>
        )}
        {scene.still && !scene.clipJob && (
          <button
            type="button"
            className="btn btn--sm"
            title={`Volver a la imagen fija (${scene.still}). El clip se queda en la galería.`}
            onClick={() => scenes.restoreStill(index)}
          >
            Volver a la imagen fija
          </button>
        )}
      </div>

      {open === "editor" && (
        <SceneImageEditor index={index} initial={scene.prompt ?? ""} onDone={() => setPanel(null)} />
      )}
      {open === "corrector" && meta?.kind === "image" && !scene.job && (
        <SceneImageCorrector index={index} initial={correctionDraft(scene.review)} onDone={() => setPanel(null)} />
      )}
    </section>
  );
}

function ReviewNote({ review }: { review: ImageReview }) {
  const note = reviewNote(review);
  return <p className={note.warn ? "hint warn" : "hint"}>{note.text}</p>;
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
