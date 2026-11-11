"use client";

import { useState } from "react";

import {
  MAX_CHARACTERS,
  castHas,
  castIn,
  mentioning,
  namesOf,
  savedNamed,
  suggestionsFor,
  withCharacter,
  type Character,
} from "@/domain/illustration";
import { useCharacters } from "@/features/illustrations/model/use-characters";
import { useImages } from "@/features/illustrations/model/use-images";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { Field } from "@/shared/ui/Field";

import { ImageChoiceSelect } from "./ImageChoiceSelect";
import { ReferenceThumb } from "./ReferenceThumb";
import { UnconfiguredProviders } from "./UnconfiguredProviders";

type Props = {
  /** Escena a la que va la imagen, o null para añadir una nueva al final. */
  index: number | null;
  /** Descripción de partida: la que ya tuviera la escena, o vacía. */
  initial: string;
  onDone: () => void;
};

/** Describir una imagen y pedirla, para una escena concreta. */
export function SceneImageEditor({ index, initial, onDone }: Props) {
  const images = useImages();
  const library = useCharacters();
  const actions = useStudioActions();
  const { busy } = useStatus();
  const [description, setDescription] = useState(initial);

  const slot = index ?? "new";
  const ready = images.choice !== null;
  const { characters } = images.guide;
  const cast = castIn(description, characters);
  const withReference = cast.filter((c) => c.saved && savedNamed(library.items, c.name)?.reference);
  /* Lo de la biblioteca solo se propone si cabe en el reparto. */
  const suggestions = suggestionsFor(description, characters, library.items).filter(
    (c) => castHas(characters, c.name) || characters.length < MAX_CHARACTERS,
  );

  /* Nombrarlo en la descripción es lo que lo pinta con sus rasgos; si viene de
     la biblioteca, además entra en el reparto del video con su referencia. */
  const add = (character: Character) => {
    setDescription((text) => mentioning(text, character.name));
    if (!castHas(characters, character.name)) images.setCharacters((c) => withCharacter(c, character));
  };

  const generate = async () => {
    if (await actions.illustrateScene(index, description)) onDone();
  };

  return (
    <div className="scene-editor">
      <Field id={`scene-image-${slot}`} label="Qué debe mostrar la imagen">
        <textarea
          id={`scene-image-${slot}`}
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Una mano que guarda monedas en una hucha de cristal, luz de mañana"
        />
      </Field>
      {suggestions.length > 0 && (
        <div className="cluster suggestions">
          <span className="hint">Sumar a la escena:</span>
          {suggestions.map((character) => (
            <button
              key={character.name}
              type="button"
              className="btn btn--sm chip"
              title={character.traits}
              onClick={() => add(character)}
            >
              <ReferenceThumb saved={character.saved ? savedNamed(library.items, character.name) : undefined} mini />
              {character.name}
            </button>
          ))}
        </div>
      )}
      {characters.length > 0 && (
        <p className="hint">
          {cast.length
            ? `${namesOf(cast)} sale${cast.length > 1 ? "n" : ""} con sus rasgos de «Personajes y elementos»${
                withReference.length ? `; ${namesOf(withReference)}, además, con su imagen de referencia` : ""
              }.`
            : "Nombra un personaje o elemento en la descripción para que salga igual que en las demás escenas."}{" "}
          El estilo visual se aplica siempre.
        </p>
      )}

      {ready ? (
        <Field id={`scene-choice-${slot}`} label="Pintar con">
          <ImageChoiceSelect id={`scene-choice-${slot}`} />
        </Field>
      ) : (
        <UnconfiguredProviders />
      )}

      <div className="cluster">
        <button
          className="btn btn--primary"
          disabled={!ready || !description.trim() || busy !== null}
          onClick={generate}
        >
          {busy === `illustrate-${slot}` ? "Pidiendo…" : "Generar imagen"}
        </button>
        <button className="btn" onClick={onDone}>
          Cancelar
        </button>
      </div>
    </div>
  );
}
