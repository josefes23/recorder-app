"use client";

import { errorPlace, type ErrorPlace } from "@/features/studio/model/error-place";
import { useStatus } from "@/features/studio/model/use-studio-actions";

/** El último error, si lo dio una acción de este sitio (o, con `only`, esa acción). */
export function ActionError({ place, only }: { place: ErrorPlace; only?: string }) {
  const { error, failedOn, setError } = useStatus();
  if (!error || errorPlace(failedOn) !== place) return null;
  // Un sitio con varios botones enseña cada error junto al suyo.
  if (only !== undefined && failedOn !== only) return null;
  return (
    <div className="action-error" role="alert">
      <p className="error">{error}</p>
      <button type="button" className="btn--icon" aria-label="Cerrar el aviso" onClick={() => setError(null)}>
        ×
      </button>
    </div>
  );
}
