export type Scene = {
  background: string | null;
  /** Segundo en el que entra. La primera escena siempre arranca en 0. */
  start: number;
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

export function appended(scenes: Scene[], background: string): Scene[] {
  const last = scenes.length ? Math.max(...scenes.map((s) => s.start)) : 0;
  return [...scenes, { background, start: scenes.length ? last + NEXT_SCENE_GAP : 0 }];
}

export const withStart = (scenes: Scene[], index: number, start: number): Scene[] =>
  scenes.map((scene, i) => (i === index ? { ...scene, start } : scene));

export const withBackground = (scenes: Scene[], index: number, background: string): Scene[] =>
  scenes.map((scene, i) => (i === index ? { ...scene, background } : scene));

export const without = (scenes: Scene[], index: number): Scene[] =>
  scenes.filter((_, i) => i !== index);
