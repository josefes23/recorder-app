/**
 * Escenas animadas: una imagen de la galería se convierte en un clip corto que
 * arranca en ella. Lo genera el servidor (Gemini Omni Flash) y llega a la
 * galería como cualquier clip. Las mismas reglas viven en
 * `app/domain/animation.py`: cambiarlas aquí obliga a cambiarlas allí.
 */

/** Con qué se anima, a qué precio orientativo y si la clave está puesta. */
export type AnimationSettings = {
  provider: string;
  name: string;
  model: string;
  resolution: string;
  /** US$ por segundo de video según el precio publicado: orientativo, no una factura. */
  usdPerSecond: number;
  ready: boolean;
  /** La variable del .env que hace falta: para decirlo en la interfaz. */
  key: string;
};

/** Límites del modelo: segundos enteros entre 3 y 15. */
export const MIN_CLIP_SECONDS = 3;
export const MAX_CLIP_SECONDS = 15;

/** Los segundos que se piden para cubrir un tramo: hacia arriba, entre 3 y 15. */
export function clipSeconds(span: number): number {
  // El margen evita que 6.0000001 (sumas de flotantes) se pida como 7.
  return Math.max(MIN_CLIP_SECONDS, Math.min(MAX_CLIP_SECONDS, Math.ceil(span - 1e-6)));
}

/** Lo que costaría animar esos tramos, en US$. */
export function estimateCost(spans: number[], usdPerSecond: number): number {
  return spans.reduce((total, span) => total + clipSeconds(span), 0) * usdPerSecond;
}

/** «US$ 3,15»: con dos decimales y coma, como el resto de la interfaz. */
export function formatUsd(value: number): string {
  return `US$ ${value.toFixed(2).replace(".", ",")}`;
}

/** Un tramo de más de 15 s queda con el clip repetido: el modelo no da más. */
export const exceedsClip = (span: number): boolean => span > MAX_CLIP_SECONDS + 1e-6;
