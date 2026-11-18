"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { MAX_ATTEMPTS } from "@/domain/illustration";
import { pendingClips, pendingImages } from "@/domain/scene";
import { AnimationControls } from "@/features/animation/ui/AnimationControls";
import { BackgroundPicker } from "@/features/backgrounds/ui/BackgroundPicker";
import { useBackgrounds } from "@/features/backgrounds/model/use-backgrounds";
import { useImages } from "@/features/illustrations/model/use-images";
import { CharactersEditor } from "@/features/illustrations/ui/CharactersEditor";
import { ImageChoiceSelect } from "@/features/illustrations/ui/ImageChoiceSelect";
import { SceneImageEditor } from "@/features/illustrations/ui/SceneImageEditor";
import { UnconfiguredProviders } from "@/features/illustrations/ui/UnconfiguredProviders";
import { useProduction } from "@/features/production/model/use-production";
import { useNarration, useSceneMedia, useScenes, useTimeline } from "@/features/scenes/model/use-scenes";
import { useScript } from "@/features/script/model/use-script";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { ActionError } from "@/features/studio/ui/ActionError";
import { useWriter } from "@/features/writer/model/use-writer";
import { Field } from "@/shared/ui/Field";
import { Lightbox } from "@/shared/ui/Lightbox";
import { Step } from "@/shared/ui/Step";

import { BulkBar } from "./BulkBar";
import { INSPECTOR_TRANSITION_ID, SceneInspector } from "./SceneInspector";
import { SceneList } from "./SceneList";
import { SceneScript } from "./SceneScript";
import { SceneTimeline } from "./SceneTimeline";
import { VideoTransition } from "./TransitionPicker";

type Props = {
  /** Panel del generador de imágenes. Lo inyecta la página, como el del guion. */
  settings?: ReactNode;
};

export function ScenesStep({ settings }: Props) {
  const scenes = useScenes();
  const backgrounds = useBackgrounds();
  const media = useSceneMedia();
  const images = useImages();
  const writer = useWriter();
  const actions = useStudioActions();
  const { busy } = useStatus();
  const { seconds, text } = useScript();
  const timeline = useTimeline();
  const production = useProduction();
  const narration = useNarration();
  /** Cómo se ven las escenas a la izquierda: en lista, o el guion partido por escenas. */
  const [view, setView] = useState<"list" | "script">("list");

  /* undefined = cerrado · null = añadir escena · número = cambiar esa escena */
  const [target, setTarget] = useState<number | null | undefined>(undefined);
  /** Escena abierta a tamaño grande, o null. */
  const [peek, setPeek] = useState<number | null>(null);
  /** El editor de imagen para una escena nueva, abierto o no. */
  const [adding, setAdding] = useState(false);
  /** La escena que enseña el inspector. */
  const [selected, setSelected] = useState(0);
  /** Las marcadas en la lista para actuar sobre varias. */
  const [checked, setChecked] = useState<ReadonlySet<number>>(() => new Set());
  const inspector = useRef<HTMLElement>(null);

  const count = scenes.items.length;
  const current = Math.min(selected, Math.max(count - 1, 0));
  /* Las marcas van por posición: si cambia el número de escenas (se añade o se
     quita una, o se rehacen todas) ya no señalan lo mismo y se sueltan. */
  const [seenCount, setSeenCount] = useState(count);
  if (seenCount !== count) {
    setSeenCount(count);
    setChecked(new Set());
  }
  const marked = [...checked].filter((i) => i < count).sort((a, b) => a - b);
  const thumbs = scenes.items.map((scene) => media(scene.background).thumb);

  const select = (index: number) => {
    setSelected(index);
    // En una pantalla estrecha el inspector queda debajo de la lista: se lleva la vista hasta él.
    requestAnimationFrame(() => inspector.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }));
  };

  /* Mover e intercambiar imágenes. La imagen cambia de sitio; el segundo y la
     transición se quedan, así que pasa a acompañar lo que se dice ahí. Cada
     cambio deja un «Deshacer», que aplica el cambio contrario (no una foto del
     estado anterior: así no se pierde una imagen que llegue entretanto). */
  const [swapping, setSwapping] = useState<number | null>(null);
  const [notice, setNotice] = useState<{ text: string; undo: () => void } | null>(null);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 8000);
    return () => clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (swapping === null) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSwapping(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [swapping]);

  const exchange = (a: number, b: number) => {
    scenes.swap(a, b);
    setChecked(new Set());
    setSwapping(null);
    select(b);
    setNotice({
      text: `Intercambiaste las imágenes de las escenas ${a + 1} y ${b + 1}.`,
      undo: () => {
        scenes.swap(a, b);
        select(a);
      },
    });
  };
  const relocate = (from: number, to: number) => {
    scenes.move(from, to);
    setChecked(new Set());
    select(to);
    setNotice({
      text: `Llevaste la imagen de la escena ${from + 1} a la ${to + 1}.`,
      undo: () => {
        scenes.move(to, from);
        select(from);
      },
    });
  };
  /* Elegir una escena: lo normal es verla en el inspector; si se está eligiendo
     con cuál intercambiar, es la otra escena del intercambio. */
  const choose = (index: number) => {
    if (swapping === null) select(index);
    else if (index === swapping) setSwapping(null);
    else exchange(swapping, index);
  };

  const peeked = peek === null ? undefined : media(scenes.items[peek]?.background).meta;

  const voice = Math.max(seconds, 1);
  const waiting = pendingImages(scenes.items);
  const animating = pendingClips(scenes.items);
  const hasScript = text.trim().length > 0;

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
      n={5}
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
        <ActionError place="scenes" />
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
          <VideoTransition />
          <SceneTimeline
            scenes={scenes.items}
            timeline={timeline}
            voiceSeconds={voice}
            thumbs={thumbs}
            selected={current}
            onSelect={choose}
            onMove={scenes.setStart}
            onSwap={exchange}
            picking={swapping !== null}
            fallback={production.transition}
            said={narration.scenes.map((part) => part.text)}
            onTransition={(i) => {
              select(i);
              // El selector de transición del inspector, ya con esa escena.
              requestAnimationFrame(() => document.getElementById(INSPECTOR_TRANSITION_ID)?.focus());
            }}
          />

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
              Los segundos no van de menor a mayor: ordénalos en el inspector para que cada escena
              dure algo y se puedan arrastrar los bordes.
            </p>
          )}

          {marked.length > 0 && <BulkBar marked={marked} onClear={() => setChecked(new Set())} />}

          {swapping !== null && (
            <div className="pick-banner" role="status">
              <span>
                Elige en la lista o en la barra la escena con la que intercambiar la imagen de la escena{" "}
                <b className="num">{swapping + 1}</b>.
              </span>
              <button type="button" className="btn btn--sm" onClick={() => setSwapping(null)}>
                Cancelar
              </button>
            </div>
          )}
          {notice && (
            <div className="undo-bar" role="status">
              <span>{notice.text}</span>
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => {
                  notice.undo();
                  setNotice(null);
                }}
              >
                Deshacer
              </button>
            </div>
          )}

          <div className="scenes-workspace">
            <div className="stack scenes-left">
              <div className="tabs" role="tablist" aria-label="Cómo ver las escenas">
                <button
                  type="button"
                  role="tab"
                  aria-selected={view === "list"}
                  className={`tab${view === "list" ? " is-on" : ""}`}
                  onClick={() => setView("list")}
                >
                  Lista
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={view === "script"}
                  className={`tab${view === "script" ? " is-on" : ""}`}
                  onClick={() => setView("script")}
                  title="El guion partido por escenas: qué se dice mientras se ve cada imagen"
                >
                  Guion por escenas
                </button>
              </div>
              {view === "script" ? (
                <SceneScript thumbs={thumbs} selected={current} onSelect={choose} />
              ) : (
                <SceneList
                  narration={narration.scenes}
                  scenes={scenes.items}
                  timeline={timeline}
                  thumbs={thumbs}
                  selected={current}
                  onSelect={choose}
                  onMove={relocate}
                  onSwap={exchange}
                  picking={swapping !== null}
                  checked={checked}
                  onCheck={(i, on) =>
                    setChecked((prev) => {
                      const next = new Set(prev);
                      if (on) next.add(i);
                      else next.delete(i);
                      return next;
                    })
                  }
                  onCheckAll={(on) => setChecked(on ? new Set(scenes.items.map((_, i) => i)) : new Set())}
                />
              )}
            </div>
            <SceneInspector
              ref={inspector}
              index={current}
              segment={timeline.segments[current]}
              previous={current > 0 ? scenes.items[current - 1] : null}
              onSelect={select}
              onPick={() => setTarget(current)}
              onPeek={() => setPeek(current)}
              onMoveImage={relocate}
              swapping={swapping === current}
              onStartSwap={() => setSwapping(swapping === current ? null : current)}
            />
          </div>
        </>
      )}

      <div className="scene-add">
        <button className="btn" onClick={() => setTarget(null)}>
          Añadir de Pexels o la galería
        </button>
        <button className="btn" disabled={adding} onClick={() => setAdding(true)}>
          Añadir con IA
        </button>
      </div>
      {adding && (
        <SceneImageEditor
          index={null}
          initial=""
          onDone={() => {
            setAdding(false);
            select(count); // la nueva va al final
          }}
        />
      )}

      {settings}

      {/* El diálogo solo elige un fondo; qué hacer con él lo decide esta feature */}
      {target !== undefined && (
        <BackgroundPicker
          onSelect={(name) => {
            scenes.place(name, target);
            if (target === null) select(count); // la nueva va al final
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
            poster: backgrounds.thumbUrl(peeked.thumb) || undefined,
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
                  select(peek);
                }}
              >
                Editar en el inspector
              </button>
            </>
          }
          onClose={() => setPeek(null)}
        />
      )}
    </Step>
  );
}
