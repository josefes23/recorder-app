/**
 * El asistente de crecimiento: ganchos, retención, títulos, SEO, puntaje y
 * tendencias. Las formas son las que valida `app/domain/growth.py`.
 *
 * Ojo con lo que son: el modelo no consulta datos en vivo de ninguna
 * plataforma. Los puntajes y las «tendencias» son criterio, no estadística.
 */

export type GrowthKind = "hooks" | "retention" | "titles" | "seo" | "score" | "trends";

export const GROWTH_KINDS: GrowthKind[] = ["hooks", "retention", "titles", "seo", "score", "trends"];

export type Hook = { text: string; type: string; why: string };
export type RetentionIssue = { at: string; problem: string; fix: string };
export type TitleIdea = { text: string; score: number; why: string };
export type ScorePart = { name: string; score: number; note: string };
export type VideoIdea = { title: string; angle: string; why: string; hook: string };
export type Trend = { topic: string; why: string };

export type GrowthResults = {
  hooks: { hooks: Hook[] };
  retention: { score: number; summary: string; issues: RetentionIssue[]; keep: string[] };
  titles: { titles: TitleIdea[] };
  seo: { score: number; tips: string[]; improved: string; tags: string[] };
  score: { total: number; parts: ScorePart[]; actions: string[] };
  trends: { ideas: VideoIdea[]; trends: Trend[]; note: string };
};

/** Qué hace falta para pedir cada consejo: el guion, o basta el tema. */
export const NEEDS_SCRIPT: Record<GrowthKind, boolean> = {
  hooks: false,
  retention: true,
  titles: false,
  seo: true,
  score: true,
  trends: false,
};

export const GROWTH_LABELS: Record<GrowthKind, string> = {
  hooks: "Ganchos",
  retention: "Retención",
  titles: "Títulos",
  seo: "SEO de la descripción",
  score: "Puntaje del video",
  trends: "Tendencias e ideas",
};

/** Por qué no se puede pedir ahora, o null si se puede. */
export function growthBlocker(kind: GrowthKind, topic: string, script: string): string | null {
  if (NEEDS_SCRIPT[kind] && !script.trim()) return "Escribe primero el guion: este consejo lo analiza.";
  if (!NEEDS_SCRIPT[kind] && !topic.trim() && !script.trim()) return "Escribe un tema o el guion.";
  return null;
}

/** Cómo se pinta un puntaje: de 0 a 100, por tramos. */
/**
 * El encargo para corregir el guion con varias recomendaciones a la vez. Se
 * manda por el mismo camino que «Aplicar» una sola: el modelo devuelve el
 * guion entero reescrito y se pregunta antes de rehacer lo que quede desfasado.
 */
export function scriptFixInstruction(items: string[]): string {
  const list = items.map((item) => item.trim()).filter(Boolean);
  return [
    "Corrige el guion aplicando TODAS estas recomendaciones a la vez. Cambia solo el guion; título y descripción quedan igual.",
    ...list.map((item, i) => `${i + 1}. ${item}`),
  ].join("\n");
}

export type ScoreTone = "bad" | "mid" | "good";

export const scoreTone = (score: number): ScoreTone => (score >= 75 ? "good" : score >= 50 ? "mid" : "bad");

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/** Comprueba la forma del consejo que llegó por el flujo de eventos. */
export function readGrowth<K extends GrowthKind>(kind: K, event: Record<string, unknown>): GrowthResults[K] {
  const result = event.result;
  if (!isObject(result)) throw new Error("El consejo llegó vacío. Vuelve a intentarlo.");
  const need = (key: string) => {
    if (!(key in result)) throw new Error("El consejo llegó incompleto. Vuelve a intentarlo.");
  };
  need(
    { hooks: "hooks", retention: "issues", titles: "titles", seo: "improved", score: "parts", trends: "ideas" }[kind],
  );
  return result as GrowthResults[K];
}

/**
 * Pone el gancho como primera frase del guion. Si el guion ya empezaba por
 * otro gancho (la misma operación antes), lo sustituye en vez de apilarlos.
 */
export function withHook(script: string, hook: string, previous: string | null = null): string {
  const text = script.trim();
  const head = hook.trim();
  const body = previous && text.startsWith(previous.trim()) ? text.slice(previous.trim().length).trim() : text;
  return body ? `${head} ${body}` : head;
}

/**
 * Lo que cambia una recomendación del puntaje. Un campo en null es un campo
 * que no cambia: que no cambie ninguno es una respuesta válida (la
 * recomendación pedía otra música, otra hora de publicación…).
 */
export type Application = {
  summary: string;
  script: string | null;
  title: string | null;
  description: string | null;
};

/** Qué hay hecho con el guion de antes que quedaría desfasado si el guion cambia. */
export type ExistingWork = {
  /** Escenas que salieron del guion visual (llevan su descripción de imagen). */
  aiScenes: number;
  /** Se puede pintar otra vez: hay un generador de imágenes configurado. */
  canPaint: boolean;
  /** Ya hay una toma de voz generada. */
  voiceTake: boolean;
};

export type Regeneration = "scenes" | "voice";

export type ApplyPlan = Application & {
  /** Qué cambia, en lenguaje llano: «el guion», «el título»… */
  changes: string[];
  /** Lo que hay que rehacer para que todo case con el guion nuevo; vacío = nada que preguntar. */
  regenerates: Regeneration[];
};

export const REGENERATION_LABELS: Record<Regeneration, string> = {
  scenes: "El guion visual y las imágenes de las escenas",
  voice: "La toma de voz",
};

/** Comprueba la forma de lo que llegó por el flujo de eventos. */
export function readApplication(event: Record<string, unknown>): Application {
  const result = event.result;
  if (!isObject(result)) throw new Error("La respuesta llegó vacía. Vuelve a intentarlo.");
  const text = (value: unknown) => (typeof value === "string" && value.trim() ? value : null);
  return {
    summary: typeof result.summary === "string" ? result.summary : "",
    script: text(result.script),
    title: text(result.title),
    description: text(result.description),
  };
}

/**
 * Qué hay que hacer para aplicarla. Solo un guion nuevo obliga a rehacer algo:
 * el título y la descripción se cambian sin más, y sin preguntar nada. Las
 * escenas manuales (clips de stock) no salen del guion, así que no cuentan.
 */
export function planApplication(application: Application, work: ExistingWork): ApplyPlan {
  const changes: string[] = [];
  if (application.script) changes.push("el guion");
  if (application.title) changes.push("el título");
  if (application.description) changes.push("la descripción");
  const regenerates: Regeneration[] = [];
  if (application.script) {
    if (work.aiScenes > 0 && work.canPaint) regenerates.push("scenes");
    if (work.voiceTake) regenerates.push("voice");
  }
  return { ...application, changes, regenerates };
}
