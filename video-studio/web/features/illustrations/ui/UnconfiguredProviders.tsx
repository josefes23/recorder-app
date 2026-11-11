"use client";

import { useImages } from "@/features/illustrations/model/use-images";

import { revealImageSettings } from "./ImageSettingsPanel";

/**
 * Atajo al panel de ajustes por cada generador al que le faltan sus datos.
 * El desplegable «Pintar con» los enseña en gris, pero no dice dónde se
 * configuran; esto lleva hasta allí con el generador ya elegido.
 */
export function UnconfiguredProviders() {
  const images = useImages();
  const missing = images.settings?.providers.filter((p) => !p.ready) ?? [];
  if (missing.length === 0) return null;

  return (
    <div className="cluster">
      {missing.map((provider) => (
        <button
          key={provider.id}
          type="button"
          className="btn btn--sm"
          onClick={() => {
            images.edit(provider.id);
            revealImageSettings();
          }}
        >
          Configurar {provider.name.split(" ")[0]}
        </button>
      ))}
      <span className="hint">
        {missing.length === 1
          ? `${missing[0].name} está sin configurar (${missing[0].note}).`
          : "Hay generadores sin configurar."}
      </span>
    </div>
  );
}
