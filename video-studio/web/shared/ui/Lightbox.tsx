"use client";

import { useEffect, type ReactNode } from "react";

export type LightboxMedia = {
  kind: "video" | "image";
  src: string;
  /** Fotograma que se enseña mientras carga el vídeo. */
  poster?: string;
};

type Props = {
  /** Cambia con el elemento: fuerza un <video> nuevo en vez de cambiar solo el src. */
  id: string | number;
  media: LightboxMedia;
  info: ReactNode;
  /** Botones de quien abre la vista; «Cerrar» lo pone la propia vista. */
  actions?: ReactNode;
  /** Sin ellos no hay flechas; con uno solo, la otra flecha sale apagada. */
  onPrev?: () => void;
  onNext?: () => void;
  onClose: () => void;
};

/**
 * Un fondo o un clip a tamaño grande y en movimiento, para decidir con calma.
 * Se pasa de uno a otro con las flechas y se cierra con Escape o clic fuera.
 */
export function Lightbox({ id, media, info, actions, onPrev, onNext, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft") onPrev?.();
      else if (e.key === "ArrowRight") onNext?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, onPrev, onNext]);

  const browsable = onPrev !== undefined || onNext !== undefined;

  return (
    <div className="lightbox" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="lightbox-box">
        <div className="lightbox-row">
          {browsable && (
            <button className="btn lightbox-nav" onClick={onPrev} disabled={!onPrev} aria-label="Anterior">
              ‹
            </button>
          )}
          <figure className="lightbox-media">
            {media.kind === "video" ? (
              <video key={id} src={media.src} poster={media.poster} autoPlay muted loop playsInline />
            ) : (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img key={id} src={media.src} alt="" />
            )}
          </figure>
          {browsable && (
            <button className="btn lightbox-nav" onClick={onNext} disabled={!onNext} aria-label="Siguiente">
              ›
            </button>
          )}
        </div>

        <div className="lightbox-info">
          <p>{info}</p>
          <div className="cluster">
            {actions}
            <button className="btn" onClick={onClose}>
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
