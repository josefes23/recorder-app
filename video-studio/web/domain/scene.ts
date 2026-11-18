import { isImageFile } from "./background.ts";
import { reviewNote, type ImageReview, type StoryboardScene } from "./illustration.ts";
import type { Transition } from "./transition.ts";

export type Scene = {
  background: string | null;
  /** Segundo en el que entra. La primera escena siempre arranca en 0. */
  start: number;
  /** Qué debe mostrar la imagen generada: lo que propuso el guion visual o lo que escribió el usuario. */
  prompt?: string;
  /**
   * Qué se mueve y qué hace la cámara si se anima: lo propone el guion visual
   * y lo cambia el usuario. Sin él, el clip lleva un movimiento sutil.
   */
  motion?: string;
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
  /**
   * Cómo entra, y cómo cambia de encuadre si es una imagen fija. Sin ella, la
   * del video (`Production.transition`).
   */
  transition?: Transition;
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

/** Claves que se quitan (no se dejan en `undefined`) al cambiar la escena. */
type Removable = Exclude<keyof Scene, "background" | "start">;

function omit(scene: Scene, ...keys: Removable[]): Scene {
  const rest = { ...scene };
  for (const key of keys) delete rest[key];
  return rest;
}

/** La escena sin rastro de animación: lo que se pidió o llegó era para la imagen de antes. */
const withoutClip = (scene: Scene): Scene => omit(scene, "still", "clipJob", "clipError");

export const withStart = (scenes: Scene[], index: number, start: number): Scene[] =>
  scenes.map((scene, i) => (i === index ? { ...scene, start } : scene));

/**
 * Cambia lo que se mueve al animar esa escena. Se guarda tal cual se escribe
 * —recortarlo a cada tecla se comería los espacios— y vacío se quita.
 */
export const withMotion = (scenes: Scene[], index: number, motion: string): Scene[] =>
  scenes.map((scene, i) => {
    if (i !== index) return scene;
    return motion ? { ...scene, motion } : omit(scene, "motion");
  });

/** Lo menos que puede durar una escena al arrastrar uno de sus bordes. */
export const MIN_DRAG_SPAN = 0.5;

/**
 * Adónde llega el inicio de la escena `index` al arrastrar su borde hasta
 * `seconds`: en décimas y sin pasar de sus vecinas, que conservan al menos
 * MIN_DRAG_SPAN. Así arrastrar nunca desordena las escenas. La primera no se
 * mueve: empieza siempre en 0.
 */
export function draggedStart(scenes: Scene[], index: number, seconds: number, total: number): number {
  const current = scenes[index]?.start ?? 0;
  if (index <= 0 || index >= scenes.length) return index === 0 ? 0 : current;
  const previous = index - 1 === 0 ? 0 : scenes[index - 1].start;
  const next = index + 1 < scenes.length ? scenes[index + 1].start : total;
  const low = Math.ceil((previous + MIN_DRAG_SPAN) * 10) / 10;
  const high = Math.floor((next - MIN_DRAG_SPAN) * 10) / 10;
  if (high < low) return current;
  return Math.min(high, Math.max(low, Math.round(seconds * 10) / 10));
}

/** En qué está una escena, para la lista compacta: lo que pide atención va primero. */
export type SceneState = "painting" | "animating" | "failed" | "review" | "empty" | "ready";

export function sceneState(scene: Scene): SceneState {
  if (scene.job) return "painting";
  if (scene.clipJob) return "animating";
  if (scene.error || scene.clipError) return "failed";
  if (!scene.background) return "empty";
  if (scene.review && reviewNote(scene.review).warn) return "review";
  return "ready";
}

/** Cambia cómo entra esa escena; null vuelve a la del video. */
export const withTransition = (scenes: Scene[], index: number, transition: Transition | null): Scene[] =>
  scenes.map((scene, i) => {
    if (i !== index) return scene;
    return transition ? { ...scene, transition } : omit(scene, "transition");
  });

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
  scenes.map((scene) => ({
    background: null,
    start: scene.start,
    prompt: scene.description,
    ...(scene.motion ? { motion: scene.motion } : {}),
  }));

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
      ? {
          background,
          start: scene.start,
          prompt: scene.prompt,
          // La imagen nueva sigue siendo la misma escena: se mueve y entra igual.
          ...(scene.motion ? { motion: scene.motion } : {}),
          ...(scene.transition ? { transition: scene.transition } : {}),
          ...(review ? { review } : {}),
        }
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

/**
 * Si tiene sentido decirle cómo moverse: lleva o espera una imagen, o ya es
 * un clip animado desde una. Un clip de Pexels ya se mueve solo.
 */
export const takesMotion = (scene: Scene): boolean =>
  Boolean(scene.still || scene.job || !scene.background || isImageFile(scene.background));

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

/** Lo que viaja al motor: fondo, segundo y, si eligió una, su transición. Lo demás es estado de la edición. */
export const forEngine = (scenes: Scene[]): Scene[] =>
  scenes.map(({ background, start, transition }) => ({ background, start, ...(transition ? { transition } : {}) }));

export const without = (scenes: Scene[], index: number): Scene[] =>
  scenes.filter((_, i) => i !== index);

// --------------------------------------------------------------------------- //
// Mover imágenes entre escenas: la imagen cambia de sitio, el tiempo no
// --------------------------------------------------------------------------- //

/**
 * Lo que es de la imagen y viaja con ella: el fondo, lo que muestra, cómo se
 * mueve, su clip, lo que se espera y lo que dijo el revisor. Se quedan en su
 * sitio el segundo (la palabra con que entra) y la transición del corte: así
 * una imagen movida pasa a acompañar lo que se dice en su nuevo sitio.
 */
type Visual = Omit<Scene, "start" | "transition">;

const visualOf = (scene: Scene): Visual => {
  const visual: Partial<Scene> = { ...scene };
  delete visual.start;
  delete visual.transition;
  return visual as Visual;
};

const inSlot = (slot: Scene, visual: Visual): Scene => ({
  ...visual,
  start: slot.start,
  ...(slot.transition ? { transition: slot.transition } : {}),
});

/** Intercambia las imágenes de dos escenas. */
export function swapImages(scenes: Scene[], a: number, b: number): Scene[] {
  if (a === b || !scenes[a] || !scenes[b]) return scenes;
  return scenes.map((scene, i) =>
    i === a ? inSlot(scene, visualOf(scenes[b])) : i === b ? inSlot(scene, visualOf(scenes[a])) : scene,
  );
}

/**
 * Lleva la imagen de la escena `from` a la escena `to`; las de en medio se
 * corren un sitio, como al reordenar una lista. Con dos vecinas es lo mismo
 * que intercambiarlas. Se deshace moviéndola de `to` a `from`.
 */
export function moveImage(scenes: Scene[], from: number, to: number): Scene[] {
  if (from === to || !scenes[from] || !scenes[to]) return scenes;
  const visuals = scenes.map(visualOf);
  const [moved] = visuals.splice(from, 1);
  visuals.splice(to, 0, moved);
  return scenes.map((slot, i) => inSlot(slot, visuals[i]));
}

/** Varias de una vez: las marcadas en la lista. */
export const withoutMany = (scenes: Scene[], indices: number[]): Scene[] =>
  scenes.filter((_, i) => !indices.includes(i));

/** La misma transición en varias escenas; null las devuelve a la del video. */
export const withTransitionOn = (scenes: Scene[], indices: number[], transition: Transition | null): Scene[] =>
  indices.reduce((acc, index) => withTransition(acc, index, transition), scenes);

/** Las escenas que no usan ese fondo: lo que queda cuando se borra de la galería. */
export const withoutBackground = (scenes: Scene[], background: string): Scene[] =>
  scenes
    .filter((scene) => scene.background !== background)
    // Si se borró la imagen de la que salió un clip, la escena se queda con el clip.
    .map((scene) => (scene.still === background ? omit(scene, "still") : scene));
