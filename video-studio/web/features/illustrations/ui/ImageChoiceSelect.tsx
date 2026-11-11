"use client";

import { choiceFromKey, choiceKey } from "@/domain/illustration";
import { useImages } from "@/features/illustrations/model/use-images";

/**
 * Con qué generador y modelo se pinta. Los generadores sin sus datos se
 * enseñan igual, en gris y sin poder elegirse: si no aparecieran, no habría
 * forma de saber que existen ni dónde se configuran.
 */
export function ImageChoiceSelect({ id }: { id: string }) {
  const images = useImages();
  if (!images.settings || !images.choice) return null;

  return (
    <select
      id={id}
      value={choiceKey(images.choice)}
      onChange={(e) => images.choose(choiceFromKey(e.target.value))}
    >
      {images.settings.providers.map((provider) => (
        <optgroup
          key={provider.id}
          label={
            provider.ready
              ? provider.name
              : `${provider.name} — sin configurar: añade sus datos en «Generador de imágenes»`
          }
        >
          {provider.models.map((model) => (
            <option
              key={model.id}
              value={choiceKey({ provider: provider.id, model: model.id })}
              disabled={!provider.ready}
            >
              {model.label} — {model.note}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
