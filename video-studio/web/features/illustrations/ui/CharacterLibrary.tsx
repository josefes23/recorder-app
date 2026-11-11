"use client";

import { MAX_CHARACTERS, castHas, fromSaved, kindLabel, withCharacter } from "@/domain/illustration";
import { useCharacters } from "@/features/illustrations/model/use-characters";
import { useImages } from "@/features/illustrations/model/use-images";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { Disclosure } from "@/shared/ui/Disclosure";

import { ReferenceThumb } from "./ReferenceThumb";

/**
 * Lo guardado desde otros videos. El guion visual ya usa lo que encaje; desde
 * aquí se mete a mano en el video, se repinta su referencia o se borra.
 */
export function CharacterLibrary() {
  const library = useCharacters();
  const images = useImages();
  const actions = useStudioActions();
  const { busy } = useStatus();
  const cast = images.guide.characters;
  const full = cast.length >= MAX_CHARACTERS;

  const remove = (id: number, name: string) => {
    if (!window.confirm(`¿Borrar «${name}» de la biblioteca? Se borra también su imagen de referencia.`)) return;
    actions.deleteSaved(id);
  };

  return (
    <Disclosure
      summary="Biblioteca"
      note={library.items.length ? `${library.items.length} guardados` : "vacía"}
    >
      {library.items.length === 0 ? (
        <p className="hint">
          Guarda un personaje o elemento con su botón «Guardar»: se le pinta una imagen de
          referencia, y en los próximos videos el guion visual lo reutiliza si encaja, con la misma
          cara, la misma ropa o la misma forma.
        </p>
      ) : (
        <div className="library-grid">
          {library.items.map((saved) => {
            const inCast = castHas(cast, saved.name);
            const painting = library.painting.includes(saved.id);
            const failure = library.failures[saved.id];
            return (
              <div className="library-card" key={saved.id}>
                <ReferenceThumb saved={saved} />
                <div className="library-card-body">
                  <div className="cluster">
                    <b>{saved.name}</b>
                    <span className="hint">{kindLabel(saved.kind)}</span>
                  </div>
                  <p className="hint library-traits" title={saved.traits}>
                    {saved.traits}
                  </p>
                  {failure && <p className="hint warn">{failure}</p>}
                  <div className="cluster">
                    <button
                      type="button"
                      className="btn btn--sm"
                      disabled={inCast || full}
                      title={full && !inCast ? `Como mucho ${MAX_CHARACTERS} por video` : undefined}
                      onClick={() => images.setCharacters((c) => withCharacter(c, fromSaved(saved)))}
                    >
                      {inCast ? "En el video" : "Usar en este video"}
                    </button>
                    <button
                      type="button"
                      className="btn btn--sm"
                      disabled={painting || busy !== null}
                      title="Pintar otra imagen de referencia, con el estilo de este video"
                      onClick={() => actions.repaintReference(saved.id)}
                    >
                      {painting ? "Pintando…" : "Rehacer imagen"}
                    </button>
                    <button
                      type="button"
                      className="btn btn--sm"
                      disabled={busy !== null}
                      onClick={() => remove(saved.id, saved.name)}
                    >
                      Borrar
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Disclosure>
  );
}
