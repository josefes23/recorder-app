"use client";

import {
  KINDS,
  MAX_CHARACTERS,
  blankCharacter,
  libraryState,
  savedNamed,
  type Character,
  type Kind,
} from "@/domain/illustration";
import { useCharacters } from "@/features/illustrations/model/use-characters";
import { useImages } from "@/features/illustrations/model/use-images";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";

import { CharacterLibrary } from "./CharacterLibrary";
import { ReferenceThumb } from "./ReferenceThumb";

const SAVE_LABEL = { unsaved: "Guardar", changed: "Guardar cambios", saved: "Guardado" } as const;

/**
 * Lo que se repite en el video: personas, animales, objetos o lugares. Lo
 * propone el guion visual; cada escena que nombra a uno lo pinta con estos
 * rasgos y, si está guardado, con su imagen de referencia.
 */
export function CharactersEditor() {
  const images = useImages();
  const library = useCharacters();
  const actions = useStudioActions();
  const { busy } = useStatus();
  const { characters } = images.guide;

  const update = (index: number, patch: Partial<Character>) =>
    images.setCharacters((cast) => cast.map((c, i) => (i === index ? { ...c, ...patch } : c)));

  return (
    <div className="characters">
      <div className="cluster characters-head">
        <span className="field-label">Personajes y elementos</span>
        <button
          type="button"
          className="btn btn--sm"
          disabled={characters.length >= MAX_CHARACTERS}
          onClick={() => images.setCharacters((cast) => [...cast, blankCharacter()])}
        >
          Añadir
        </button>
      </div>

      {characters.length === 0 ? (
        <p className="hint">
          Los propone el guion visual: personas, animales, objetos o lugares que se repiten, y los
          de tu biblioteca que encajen. Una escena que nombre a uno lo pinta con sus rasgos, igual en
          todas.
        </p>
      ) : (
        characters.map((character, i) => {
          const saved = savedNamed(library.items, character.name);
          const state = libraryState(character, library.items);
          const label = character.name.trim() || `el elemento ${i + 1}`;
          const failure = saved ? library.failures[saved.id] : undefined;
          return (
            <div className="character" key={i}>
              <ReferenceThumb saved={character.saved ? saved : undefined} />
              <div className="character-id">
                <input
                  aria-label={`Nombre del elemento ${i + 1}`}
                  value={character.name}
                  placeholder="Nombre"
                  // Otro nombre es otro elemento: deja de usar la referencia del guardado.
                  onChange={(e) => update(i, { name: e.target.value, saved: null })}
                />
                <select
                  aria-label={`Tipo de ${label}`}
                  value={character.kind}
                  onChange={(e) => update(i, { kind: e.target.value as Kind })}
                >
                  {KINDS.map((kind) => (
                    <option key={kind.id} value={kind.id}>
                      {kind.label}
                    </option>
                  ))}
                </select>
              </div>
              <textarea
                aria-label={`Rasgos de ${label}`}
                rows={3}
                value={character.traits}
                placeholder={
                  character.kind === "persona"
                    ? "Edad, cara, pelo, ropa con sus colores…"
                    : "Forma, tamaño, materiales, colores, lo que lo distingue…"
                }
                onChange={(e) => update(i, { traits: e.target.value })}
              />
              <div className="character-actions">
                <button
                  type="button"
                  className="btn btn--sm"
                  disabled={
                    state === "saved" || busy !== null || !character.name.trim() || !character.traits.trim()
                  }
                  title={
                    state === "saved"
                      ? "Ya está en la biblioteca con estos rasgos"
                      : "Guardarlo en la biblioteca con una imagen de referencia, para reutilizarlo en otros videos"
                  }
                  onClick={() => actions.saveCharacter(i)}
                >
                  {busy === `save-character-${i}` ? "Guardando…" : SAVE_LABEL[state]}
                </button>
                <button
                  type="button"
                  className="btn btn--icon"
                  title={`Quitar ${label} de este video`}
                  onClick={() => images.setCharacters((cast) => cast.filter((_, j) => j !== i))}
                >
                  ×
                </button>
              </div>
              {failure && <p className="hint warn character-note">{failure}</p>}
            </div>
          );
        })
      )}

      <CharacterLibrary />
    </div>
  );
}
