"use client";

import type { SavedCharacter } from "@/domain/illustration";
import { useCharacters } from "@/features/illustrations/model/use-characters";

type Props = {
  saved: SavedCharacter | undefined;
  /** Pequeña, para ir junto a un nombre en una lista. */
  mini?: boolean;
};

/** La imagen de referencia de un elemento guardado: la que lo mantiene igual de un video a otro. */
export function ReferenceThumb({ saved, mini = false }: Props) {
  const library = useCharacters();
  const className = mini ? "ref-thumb ref-thumb--mini" : "ref-thumb";
  if (saved && library.painting.includes(saved.id)) {
    return <span className={`${className} ref-thumb--busy`} title="Pintando su imagen de referencia…" />;
  }
  const url = saved ? library.referenceUrl(saved) : null;
  if (!saved || !url) {
    return (
      <span
        className={`${className} ref-thumb--empty`}
        title={saved ? "Aún sin imagen de referencia" : "Sin guardar: no tiene imagen de referencia"}
      />
    );
  }
  return (
    <a href={url} target="_blank" rel="noreferrer" title={`Ver la imagen de referencia de ${saved.name}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className={className} src={url} alt={`Referencia de ${saved.name}`} />
    </a>
  );
}
