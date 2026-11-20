/**
 * El acabado de un video: lo que se le hace una vez armado para que suene y se
 * vea mejor. Cuatro cosas, todas opcionales y apagadas por defecto: audio,
 * color, ritmo y tarjetas de entrada y cierre. Las mismas reglas viven en
 * `app/domain/finish.py`; los ajustes viajan con la producción y se guardan
 * dentro del estilo del video, de donde «Reutilizar» los recupera.
 */

export type LookId = "none" | "warm" | "cool" | "cine" | "vivid" | "mono";

export const LOOKS: { id: LookId; label: string; hint: string }[] = [
  { id: "none", label: "Natural", hint: "Sin tocar el color" },
  { id: "warm", label: "Cálido", hint: "Tonos dorados, más cercano" },
  { id: "cool", label: "Frío", hint: "Tonos azulados, más limpio" },
  { id: "cine", label: "Cine", hint: "Sombras verdosas, luces anaranjadas" },
  { id: "vivid", label: "Vivo", hint: "Más contraste y más color" },
  { id: "mono", label: "Blanco y negro", hint: "Sin color" },
];

export type Finish = {
  audio: {
    /** Quita graves que ensucian, iguala el volumen de la voz y le da presencia. */
    clean: boolean;
    /** Lleva la mezcla final (voz y música) a -14 LUFS, el nivel de las redes. */
    normalize: boolean;
  };
  color: {
    look: LookId;
    /** Cada ajuste va de -1 a 1; 0 no cambia nada. */
    exposure: number;
    contrast: number;
    saturation: number;
  };
  pace: {
    /** Acorta las pausas largas de la voz; los subtítulos y las escenas se re-sincronizan solos. */
    tighten: boolean;
  };
  cards: {
    /** Texto de la tarjeta de entrada (admite *resaltado*); vacío = sin tarjeta. */
    intro: string;
    /** Texto de la tarjeta de cierre; vacío = sin tarjeta. */
    outro: string;
  };
};

export const DEFAULT_FINISH: Finish = {
  audio: { clean: false, normalize: false },
  color: { look: "none", exposure: 0, contrast: 0, saturation: 0 },
  pace: { tighten: false },
  cards: { intro: "", outro: "" },
};

/** Los mismos límites que el servidor. */
export const INTRO_LIMIT = 90;
export const OUTRO_LIMIT = 120;
export const INTRO_SECONDS = 1.6;
export const OUTRO_SECONDS = 2.6;

const isLook = (value: unknown): value is LookId => LOOKS.some((look) => look.id === value);
const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const adjust = (value: unknown): number =>
  typeof value === "number" && Number.isFinite(value) ? Math.max(-1, Math.min(1, Math.round(value * 100) / 100)) : 0;

const line = (value: unknown, limit: number): string =>
  typeof value === "string" ? value.split(/\s+/).filter(Boolean).join(" ").slice(0, limit) : "";

/** El acabado de un video guardado; lo que no vale se ignora, un video de antes sale sin retoques. */
export function readFinish(raw: unknown): Finish {
  const data = isObject(raw) ? raw : {};
  const audio = isObject(data.audio) ? data.audio : {};
  const color = isObject(data.color) ? data.color : {};
  const pace = isObject(data.pace) ? data.pace : {};
  const cards = isObject(data.cards) ? data.cards : {};
  return {
    audio: { clean: audio.clean === true, normalize: audio.normalize === true },
    color: {
      look: isLook(color.look) ? color.look : "none",
      exposure: adjust(color.exposure),
      contrast: adjust(color.contrast),
      saturation: adjust(color.saturation),
    },
    pace: { tighten: pace.tighten === true },
    cards: { intro: line(cards.intro, INTRO_LIMIT), outro: line(cards.outro, OUTRO_LIMIT) },
  };
}

export const colorActive = (color: Finish["color"]): boolean =>
  color.look !== "none" || color.exposure !== 0 || color.contrast !== 0 || color.saturation !== 0;

/** Qué retoques hay puestos, en palabras: para la nota del paso. Vacío si no hay ninguno. */
export function finishSummary(finish: Finish): string[] {
  const parts: string[] = [];
  if (finish.audio.clean || finish.audio.normalize) parts.push("audio");
  if (colorActive(finish.color)) parts.push("color");
  if (finish.pace.tighten) parts.push("ritmo");
  if (finish.cards.intro || finish.cards.outro) parts.push("tarjetas");
  return parts;
}

/**
 * Lo que se va a aplicar al renderizar, en palabras claras: para el resumen
 * junto al botón de Renderizar. Vacío si no hay ningún retoque.
 */
export function finishDetails(finish: Finish): string[] {
  const details: string[] = [];
  if (finish.audio.clean) details.push("voz con presencia");
  if (finish.audio.normalize) details.push("volumen a −14 LUFS");
  if (colorActive(finish.color)) {
    const look = LOOKS.find((item) => item.id === finish.color.look);
    details.push(look && look.id !== "none" ? `color ${look.label}` : "color ajustado");
  }
  if (finish.pace.tighten) details.push("pausas recortadas");
  const cards = [finish.cards.intro && "entrada", finish.cards.outro && "cierre"].filter(Boolean);
  if (cards.length) details.push(`tarjeta de ${cards.join(" y ")}`);
  return details;
}

/** Lo que casi siempre conviene y no cambia cómo se ve: audio y ritmo. Sin color ni tarjetas, que son de gusto. */
export const isRecommended = (finish: Finish): boolean =>
  finish.audio.clean && finish.audio.normalize && finish.pace.tighten;

/** Aplica lo recomendado sin tocar el color ni las tarjetas que ya se hayan elegido. */
export const withRecommended = (finish: Finish): Finish => ({
  ...finish,
  audio: { clean: true, normalize: true },
  pace: { tighten: true },
});

/** Cuánto se alarga el video con las tarjetas, en segundos. */
export const cardsSeconds = (cards: Finish["cards"]): number =>
  (cards.intro ? INTRO_SECONDS : 0) + (cards.outro ? OUTRO_SECONDS : 0);
