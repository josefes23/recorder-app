import { isImageFile } from "./background.ts";
import type { ImageReview, StoryboardScene } from "./illustration";

export type Scene = {
  background: string | null;
  /** Segundo en el que entra. La primera escena siempre arranca en 0. */
  start: number;
  /** Qué debe mostrar la imagen generada: lo que propuso el guion visual o lo que escribió el usuario. */
  prompt?: string;
  /** Imagen pedida que aún no ha llegado. */
  job?: string;
  /** Por qué falló la última imagen pedida. */
  error?: string;
  /** Lo que dijo el revisor de la imagen generada que lleva. */
  review?: ImageReview;
  /**
   * La imagen de la que salió el clip animado que lleva ahora. Sirve para
   * volver a ella o animarla otra vez; sin animar, no hay.
   */
  still?: string;
  /** Clip animado pedido que aún no ha llegado. */
  clipJob?: string;
  /** Por qué falló la última animación pedida. */
  clipError?: string;
};

export type TimelineSegment = {
  start: number;
  /** Segundo en el que la releva la siguiente escena, o el final del vídeo. */
  end: number;
  /** Cuánto dura el tramo hasta que entra la siguiente escena. */
  span: number;
  /** Entra después de que acabe la voz, así que no llega a verse. */
  late: boolean;
  /**
   * Veces que el motor encadenará el clip para cubrir el tramo; 1 es que no se
   * repite. Misma cuenta que `build_background` en el generador, para que el
   * número que se enseña sea el que va a pasar de verdad.
   */
  repeats: number;
};

export type Timeline = {
  /** Hasta dónde llega la barra: la voz, o la última escena si se pasa de ella. */
  total: number;
  segments: TimelineSegment[];
  /** Números de escena (empezando en 1) que entran tarde. */
  late: number[];
  /** Los segundos no van de menor a mayor, así que hay tramos sin duración. */
  disordered: boolean;
};

/** Hueco mínimo para que un tramo siga siendo visible en la barra. */
const MIN_SPAN = 0.2;

/**
 * @param clipSeconds duración de cada fondo, en el mismo orden que las escenas.
 *   Cero para imágenes o para lo que no se conozca: no se repiten.
 */
export function buildTimeline(
  scenes: Scene[],
  voiceSeconds: number,
  clipSeconds: number[] = [],
): Timeline {
  const voice = Math.max(voiceSeconds, 1);
  const starts = scenes.map((scene, i) => (i === 0 ? 0 : scene.start));
  const total = Math.max(voice, ...starts);

  const segments = starts.map((start, i) => {
    const end = i + 1 < starts.length ? starts[i + 1] : total;
    const span = Math.max(MIN_SPAN, end - start);
    const clip = clipSeconds[i] ?? 0;
    return {
      start,
      end,
      span,
      late: start >= voice,
      repeats: clip > 0 && span > clip ? Math.floor(span / clip) + 1 : 1,
    };
  });

  return {
    total,
    segments,
    late: segments.flatMap((segment, i) => (segment.late ? [i + 1] : [])),
    disordered: starts.some((start, i) => i > 0 && start < starts[i - 1]),
  };
}

/** Separación por defecto al encadenar una escena nueva al final. */
const NEXT_SCENE_GAP = 8;

export function appended(scenes: Scene[], background: string | null): Scene[] {
  const last = scenes.length ? Math.max(...scenes.map((s) => s.start)) : 0;
  return [...scenes, { background, start: scenes.length ? last + NEXT_SCENE_GAP : 0 }];
}

/** Claves de estado que se quitan (no se dejan en `undefined`) al cambiar la escena. */
type Transient = "still" | "clipJob" | "clipError";

function omit(scene: Scene, ...keys: Transient[]): Scene {
  const rest = { ...scene };
  for (const key of keys) delete rest[key];
  return rest;
}

/** La escena sin rastro de animación: lo que se pidió o llegó era para la imagen de antes. */
const withoutClip = (scene: Scene): Scene => omit(scene, "still", "clipJob", "clipError");

export const withStart = (scenes: Scene[], index: number, start: number): Scene[] =>
  scenes.map((scene, i) => (i === index ? { ...scene, start } : scene));

/**
 * Pone un fondo elegido a mano. Si la escena esperaba una imagen, deja de
 * esperarla: lo que el usuario eligió después manda sobre lo que pidió antes.
 */
export const withBackground = (scenes: Scene[], index: number, background: string): Scene[] =>
  scenes.map((scene, i) =>
    i === index
      ? { ...withoutClip(scene), background, job: undefined, error: undefined, review: undefined }
      : scene,
  );

/** Escenas nuevas desde el guion visual, aún sin imagen: se marcan según sale cada encargo. */
export const fromStoryboard = (scenes: StoryboardScene[]): Scene[] =>
  scenes.map((scene) => ({ background: null, start: scene.start, prompt: scene.description }));

/** Marca la escena como «pintándose»; `null` la añade al final. */
export function withJob(scenes: Scene[], index: number | null, job: string, prompt: string): Scene[] {
  const target = index ?? scenes.length;
  const base = index === null ? appended(scenes, null) : scenes;
  return base.map((scene, i) =>
    i === target ? { ...withoutClip(scene), job, prompt, error: undefined, review: undefined } : scene,
  );
}

/** Llegó la imagen: la escena que la esperaba la estrena. Si ya no la espera nadie, nada cambia. */
export const withImage = (
  scenes: Scene[],
  job: string,
  background: string,
  review: ImageReview | null = null,
): Scene[] =>
  scenes.map((scene) =>
    scene.job === job
      ? { background, start: scene.start, prompt: scene.prompt, ...(review ? { review } : {}) }
      : scene,
  );

export const withFailure = (scenes: Scene[], job: string, error: string): Scene[] =>
  scenes.map((scene) => (scene.job === job ? { ...scene, job: undefined, error } : scene));

export const pendingImages = (scenes: Scene[]): number => scenes.filter((s) => s.job).length;

// --------------------------------------------------------------------------- //
// Animación: la imagen de la escena se convierte en un clip
// --------------------------------------------------------------------------- //

/**
 * La imagen que se anima: la original si la escena ya lleva un clip animado
 * (animar otra vez parte de ella, no del clip), o la imagen que lleva. Null si
 * no hay ninguna, o si espera algo.
 */
export function animatable(scene: Scene): string | null {
  if (scene.job || scene.clipJob) return null;
  if (scene.still) return scene.still;
  return scene.background && isImageFile(scene.background) ? scene.background : null;
}

/** Marca esa escena como «animándose». */
export const withClipJobAt = (scenes: Scene[], index: number, clipJob: string): Scene[] =>
  scenes.map((scene, i) => (i === index ? { ...omit(scene, "clipError"), clipJob } : scene));

/**
 * Lo mismo, pero buscando la escena por su imagen: para animar sola la imagen
 * que acaba de llegar, cuando su posición pudo cambiar entretanto.
 */
export const withClipJobOn = (scenes: Scene[], background: string, clipJob: string): Scene[] =>
  scenes.map((scene) =>
    scene.background === background && !scene.clipJob
      ? { ...omit(scene, "clipError"), clipJob }
      : scene,
  );

/**
 * Llegó el clip: la escena que lo esperaba lo estrena y guarda su imagen para
 * poder volver. Si ya no lo espera nadie (se cambió la imagen), nada cambia.
 */
export function withClip(scenes: Scene[], clipJob: string, clip: string): Scene[] {
  return scenes.map((scene) => {
    if (scene.clipJob !== clipJob) return scene;
    const still = scene.still ?? scene.background;
    return { ...withoutClip(scene), ...(still ? { still } : {}), background: clip };
  });
}

export const withClipFailure = (scenes: Scene[], clipJob: string, error: string): Scene[] =>
  scenes.map((scene) =>
    scene.clipJob === clipJob ? { ...omit(scene, "clipJob"), clipError: error } : scene,
  );

/** No se pudo ni pedir: el error queda en la escena de esa imagen. */
export const withClipFailureOn = (scenes: Scene[], background: string, error: string): Scene[] =>
  scenes.map((scene) =>
    scene.background === background && !scene.clipJob ? { ...scene, clipError: error } : scene,
  );

/** Vuelve a la imagen fija de la que salió el clip. El clip se queda en la galería. */
export const withStillImage = (scenes: Scene[], index: number): Scene[] =>
  scenes.map((scene, i) =>
    i === index && scene.still ? { ...withoutClip(scene), background: scene.still } : scene,
  );

export const pendingClips = (scenes: Scene[]): number => scenes.filter((s) => s.clipJob).length;

/** Lo que viaja al motor: fondo y segundo. Lo demás es estado de la edición. */
export const forEngine = (scenes: Scene[]): Scene[] =>
  scenes.map(({ background, start }) => ({ background, start }));

export const without = (scenes: Scene[], index: number): Scene[] =>
  scenes.filter((_, i) => i !== index);

/** Las escenas que no usan ese fondo: lo que queda cuando se borra de la galería. */
export const withoutBackground = (scenes: Scene[], background: string): Scene[] =>
  scenes
    .filter((scene) => scene.background !== background)
    // Si se borró la imagen de la que salió un clip, la escena se queda con el clip.
    .map((scene) => (scene.still === background ? omit(scene, "still") : scene));
