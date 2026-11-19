"use client";

import { useState } from "react";

import {
  COVER_DESIGNS,
  IDEAL_TITLE_WORDS,
  coverCandidates,
  coverImagePrompt,
  titleParts,
  titleWords,
} from "@/domain/cover";
import { useBackgrounds } from "@/features/backgrounds/model/use-backgrounds";
import { useCover } from "@/features/cover/model/use-cover";
import { useImages } from "@/features/illustrations/model/use-images";
import { useScenes } from "@/features/scenes/model/use-scenes";
import { useScript } from "@/features/script/model/use-script";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";
import { ActionError } from "@/features/studio/ui/ActionError";
import { useWriter } from "@/features/writer/model/use-writer";

/** El título como saldrá: lo resaltado, resaltado. */
function TitlePreview({ title }: { title: string }) {
  return (
    <>
      {titleParts(title).map((part, i) => (
        <span key={i}>
          {i > 0 && " "}
          {part.highlighted ? <mark>{part.text}</mark> : part.text}
        </span>
      ))}
    </>
  );
}

/**
 * Lo que se puede cambiar de la portada si no convence: el título (a mano o
 * entre los que proponga el modelo), el diseño y la imagen. Cada cambio la
 * repinta sola.
 */
export function CoverControls() {
  const cover = useCover();
  const script = useScript();
  const scenes = useScenes();
  const backgrounds = useBackgrounds();
  const images = useImages();
  const writer = useWriter();
  const actions = useStudioActions();

  const [asking, setAsking] = useState(false);
  const [description, setDescription] = useState("");

  const title = cover.draft.title ?? cover.resolved?.title ?? "";
  const words = titleWords(title);
  const selected = cover.resolved?.background ?? null;
  // Una imagen pintada solo para la portada no está en ninguna escena, pero se elige igual.
  const candidates = coverCandidates(scenes.items);
  if (selected && !candidates.includes(selected)) candidates.push(selected);

  const openAsk = () => {
    setDescription(coverImagePrompt(script.topic, scenes.items.find((s) => s.prompt)?.prompt));
    setAsking(true);
  };

  return (
    <div className="stack">
      <div className="field">
        <label htmlFor="cover-title">Título de la portada</label>
        <input
          id="cover-title"
          value={title}
          placeholder="El *error* que todos cometen"
          onChange={(e) => cover.setTitle(e.target.value)}
        />
        <p className={`hint${words > IDEAL_TITLE_WORDS ? " warn" : ""}`}>
          {words > IDEAL_TITLE_WORDS
            ? `Lleva ${words} palabras: en miniatura se leen bien hasta ${IDEAL_TITLE_WORDS}.`
            : "Lo que va entre *asteriscos* sale resaltado en otro color."}
        </p>
      </div>

      <ActionError place="cover" />
      {writer.label && (
        <div className="stack cover-suggest">
          <button
            className="btn btn--sm"
            disabled={cover.suggesting}
            onClick={actions.suggestTitles}
          >
            {cover.suggesting
              ? "Pensando títulos…"
              : cover.suggestions.length
                ? "Otros títulos"
                : "Sugerir títulos con IA"}
          </button>
          {cover.suggestions.length > 0 && (
            <div className="cover-titles" role="list">
              {cover.suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  role="listitem"
                  className={`cover-title${suggestion === title ? " is-on" : ""}`}
                  onClick={() => cover.setTitle(suggestion)}
                >
                  <TitlePreview title={suggestion} />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="field">
        <span className="field-label">Diseño</span>
        <div className="tabs" role="radiogroup" aria-label="Diseño de la portada">
          {COVER_DESIGNS.map((design) => (
            <button
              key={design.id}
              role="radio"
              aria-checked={cover.draft.design === design.id}
              className={`tab${cover.draft.design === design.id ? " is-on" : ""}`}
              title={design.hint}
              onClick={() => cover.setDesign(design.id)}
            >
              {design.label}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <span className="field-label">Imagen</span>
        <div className="cover-strip">
          {candidates.map((name) => {
            const meta = backgrounds.items.find((b) => b.name === name);
            const thumb = meta?.thumb ? backgrounds.thumbUrl(meta.thumb) : null;
            return (
              <button
                key={name}
                className={`cover-pick${name === selected ? " is-on" : ""}`}
                title={name}
                aria-pressed={name === selected}
                // La automática se elige como «automática»: así sigue a las escenas si cambian.
                onClick={() => cover.setBackground(name === cover.automatic ? null : name)}
              >
                {/* Sin miniatura (o con la galería aún cargando), un hueco del mismo tamaño */}
                {thumb ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img className="scene-thumb" src={thumb} alt="" />
                ) : (
                  <span className="scene-thumb" aria-hidden="true" />
                )}
              </button>
            );
          })}
          {cover.illustrating && (
            <span className="scene-thumb scene-thumb--busy" title="Pintando la imagen de la portada…" />
          )}
          {images.choice && !cover.illustrating && (
            <button
              className="scene-thumb scene-thumb--empty cover-ai"
              title="Pintar una imagen solo para la portada"
              onClick={() => (asking ? setAsking(false) : openAsk())}
            >
              IA
            </button>
          )}
        </div>
        {candidates.length === 0 && (
          <p className="hint">
            Sin escenas, la portada lleva el degradado del tema. Elige fondos en el paso 7
            {images.choice ? " o pinta una imagen con IA." : "."}
          </p>
        )}
      </div>

      {asking && (
        <div className="ai-panel">
          <label className="field-label" htmlFor="cover-ai">
            Qué debe mostrar la imagen de portada
          </label>
          <textarea
            id="cover-ai"
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="cluster">
            <button
              className="btn btn--sm btn--primary"
              disabled={cover.illustrating || !description.trim()}
              onClick={async () => {
                setAsking(false);
                await actions.illustrateCover(description);
              }}
            >
              Pintar imagen
            </button>
            <button className="btn btn--sm" onClick={() => setAsking(false)}>
              Cancelar
            </button>
          </div>
          <p className="hint">
            Con el estilo y el reparto del video. Entra en la galería como cualquier imagen y la
            portada la usa en cuanto llega.
          </p>
        </div>
      )}
    </div>
  );
}
