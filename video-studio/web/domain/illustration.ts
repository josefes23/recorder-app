/** Quién pinta las imágenes de las escenas: generador, datos y modelo. */

export type ImageField = {
  /** Variable del .env donde se guarda. */
  env: string;
  label: string;
  /** Una clave: se enmascara y se escribe en un campo de contraseña. */
  secret: boolean;
  /** Lo guardado (enmascarado si es secreto), o null si falta. */
  hint: string | null;
};

export type ImageModel = { id: string; label: string; note: string };

export type ImageProvider = {
  id: string;
  name: string;
  note: string;
  /** Tiene todos sus datos guardados: puede pintar ya. */
  ready: boolean;
  fields: ImageField[];
  model: string;
  models: ImageModel[];
};

export type ImageSettings = {
  /** El generador elegido, tenga datos o no. */
  provider: string;
  /** Generador y modelo que pintarán por defecto, o null si ninguno está listo. */
  label: string | null;
  /** Estilo propuesto para las imágenes. */
  style: string;
  providers: ImageProvider[];
};

export type ImageSettingsDraft = {
  provider: string;
  model: string;
  /** Variable del .env → valor. Uno vacío conserva el que hubiera. */
  values: Record<string, string>;
};

/** Con qué se pinta una imagen concreta. */
export type ImageChoice = { provider: string; model: string };

/** Qué es cada elemento que se repite. Igual que `KINDS` en el backend. */
export type Kind = "persona" | "animal" | "objeto" | "lugar";

export const KINDS: { id: Kind; label: string }[] = [
  { id: "persona", label: "Persona" },
  { id: "animal", label: "Animal" },
  { id: "objeto", label: "Objeto" },
  { id: "lugar", label: "Lugar" },
];

export const isKind = (value: unknown): value is Kind => KINDS.some((k) => k.id === value);

export const kindLabel = (kind: Kind): string => KINDS.find((k) => k.id === kind)?.label ?? kind;

/**
 * Algo que sale en varias escenas con los rasgos que no cambian: una persona,
 * un animal, un objeto (una máquina, un juguete, un juego) o un lugar.
 */
export type Character = {
  name: string;
  traits: string;
  kind: Kind;
  /** Id en la biblioteca si viene de ahí: su imagen de referencia acompaña a cada escena donde sale. */
  saved: number | null;
};

export const blankCharacter = (): Character => ({ name: "", traits: "", kind: "persona", saved: null });

/** Un elemento de la biblioteca, guardado desde un video para reutilizarlo en otros. */
export type SavedCharacter = {
  id: number;
  name: string;
  traits: string;
  kind: Kind;
  /** Archivo de su imagen de referencia, o null mientras se pinta. */
  reference: string | null;
  created_at: string;
  updated_at: string;
};

/**
 * Lo que comparten todas las imágenes de un video para parecer del mismo:
 * estilo, reparto y semilla. El generador pinta cada escena sin ver las
 * demás, así que esto viaja con cada encargo.
 */
export type VisualGuide = {
  look: string;
  characters: Character[];
  /** null: la que quiera el generador. */
  seed: number | null;
};

/** Una escena del guion visual: cuándo entra, qué dice la voz y qué se ve. */
export type StoryboardScene = { start: number; text: string; description: string };

export type Storyboard = { guide: VisualGuide; scenes: StoryboardScene[] };

/** Igual que `MAX_CHARACTERS` en el backend. */
export const MAX_CHARACTERS = 6;

const fold = (text: string): string =>
  text.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, " ").trim();

const escapeRegExp = (text: string): string => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * Los personajes que nombra una descripción: solo esos salen con sus rasgos.
 * Misma regla que `cast_in` en el backend: el nombre entero, sin mirar
 * tildes ni mayúsculas.
 */
export function castIn(description: string, characters: Character[]): Character[] {
  const plain = fold(description);
  return characters.filter((c) => {
    const name = fold(c.name);
    return name.length > 0 && new RegExp(`\\b${escapeRegExp(name)}\\b`).test(plain);
  });
}

/** «Ana», «Ana y Luis», «Ana, Luis y Eva». */
export function namesOf(characters: Character[]): string {
  const names = characters.map((c) => c.name.trim()).filter(Boolean);
  return names.length > 1 ? `${names.slice(0, -1).join(", ")} y ${names.at(-1)}` : (names[0] ?? "");
}

export const imageProviderOf = (settings: ImageSettings, id: string): ImageProvider =>
  settings.providers.find((p) => p.id === id) ?? settings.providers[0];

/** Se puede guardar si cada dato ya está guardado o se acaba de escribir. */
export const canSaveImages = (provider: ImageProvider, typed: Record<string, string>): boolean =>
  provider.fields.every((f) => Boolean(f.hint) || (typed[f.env] ?? "").trim().length > 0);

/** Cada modelo de cada generador listo, para elegir con qué pintar. */
export function readyChoices(
  settings: ImageSettings | null,
): Array<ImageChoice & { label: string; note: string }> {
  if (!settings) return [];
  return settings.providers
    .filter((p) => p.ready)
    .flatMap((p) =>
      p.models.map((m) => ({
        provider: p.id,
        model: m.id,
        label: `${p.name.split(" ")[0]} · ${m.label}`,
        note: m.note,
      })),
    );
}

/**
 * El generador elegido si está listo, con su modelo guardado; si no, el
 * primero que lo esté. Misma regla que `ImageSettings.active` en el backend.
 */
export function defaultChoice(settings: ImageSettings | null): ImageChoice | null {
  if (!settings) return null;
  const chosen = imageProviderOf(settings, settings.provider);
  const provider = chosen?.ready ? chosen : settings.providers.find((p) => p.ready);
  return provider ? { provider: provider.id, model: provider.model } : null;
}

export const choiceKey = (choice: ImageChoice): string => `${choice.provider}|${choice.model}`;

export function choiceFromKey(key: string): ImageChoice {
  const [provider, ...rest] = key.split("|");
  return { provider, model: rest.join("|") };
}

/** La elección sigue valiendo si su generador sigue listo y ofrece ese modelo. */
export const isAvailable = (settings: ImageSettings | null, choice: ImageChoice | null): boolean =>
  Boolean(choice) &&
  readyChoices(settings).some((c) => c.provider === choice!.provider && c.model === choice!.model);

/**
 * Lo que dijo el modelo del guion de una imagen antes de darla por buena.
 * Igual que `ReviewReport` en el backend.
 */
export type ImageReview = {
  /** approved: la vio y vale · flagged: ningún intento quedó limpio · unchecked: no se pudo revisar. */
  status: "approved" | "flagged" | "unchecked";
  /** Quién revisó: «Claude», «Google · gemini-3.6-flash». */
  reviewer: string;
  /** Imágenes pintadas para la escena. */
  attempts: number;
  /** Fallos de la imagen que se quedó. */
  problems: string[];
  /** Fallos de las que se descartaron por el camino. */
  fixed: string[];
  /** Por qué no se pudo revisar. */
  detail: string;
};

/** Imágenes que se pintan como mucho por escena. Igual que `MAX_ATTEMPTS` en el backend. */
export const MAX_ATTEMPTS = 3;

const REVIEW_STATUSES: readonly string[] = ["approved", "flagged", "unchecked"];

const texts = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

/** La revisión que llega con la imagen, o null si no la hubo o llegó rota. */
export function readReview(value: unknown): ImageReview | null {
  const raw = value as Partial<ImageReview> | null | undefined;
  if (!raw || typeof raw.status !== "string" || !REVIEW_STATUSES.includes(raw.status)) return null;
  return {
    status: raw.status,
    reviewer: typeof raw.reviewer === "string" && raw.reviewer ? raw.reviewer : "El revisor",
    attempts: typeof raw.attempts === "number" && raw.attempts > 0 ? raw.attempts : 1,
    problems: texts(raw.problems),
    fixed: texts(raw.fixed),
    detail: typeof raw.detail === "string" ? raw.detail : "",
  };
}

const sentence = (items: string[]): string => items.join("; ").replace(/[.\s]+$/, "");

/** La línea que se enseña debajo de la escena, y si es un aviso. */
export function reviewNote(review: ImageReview): { text: string; warn: boolean } {
  const { reviewer, attempts } = review;
  if (review.status === "unchecked") {
    return { text: `Sin revisar: ${review.detail || "el revisor no contestó"}`, warn: true };
  }
  if (review.status === "flagged") {
    const tries = attempts === 1 ? "1 intento" : `${attempts} intentos`;
    return {
      text: `${reviewer} ve fallos tras ${tries}: ${sentence(review.problems)}. Corrígela, pide otra o elige otro fondo.`,
      warn: true,
    };
  }
  const dropped = attempts - 1;
  if (dropped === 0) return { text: `Revisada por ${reviewer}.`, warn: false };
  const images = dropped === 1 ? "1 imagen" : `${dropped} imágenes`;
  const why = review.fixed.length ? `: ${sentence(review.fixed)}` : "";
  return { text: `Revisada por ${reviewer}. Descartó ${images} con fallos${why}.`, warn: false };
}

// --------------------------------------------------------------------------- //
// Corregir una imagen
// --------------------------------------------------------------------------- //

/** Tope de lo que se cuenta que está mal. Igual que `CORRECTION_LIMIT` en el backend. */
export const CORRECTION_LIMIT = 500;

/**
 * De qué partir al corregir: si el revisor vio fallos en la imagen que se
 * quedó, esos mismos, ya redactados; si no, nada.
 */
export function correctionDraft(review: ImageReview | undefined | null): string {
  if (review?.status !== "flagged") return "";
  const problems = review.problems.map((p) => p.trim().replace(/[.\s]+$/, "")).filter(Boolean);
  return problems.length ? `${problems.join("; ")}.` : "";
}

// --------------------------------------------------------------------------- //
// Biblioteca de elementos
// --------------------------------------------------------------------------- //

/** El elemento guardado, listo para entrar en el reparto de un video. */
export const fromSaved = (saved: SavedCharacter): Character => ({
  name: saved.name,
  traits: saved.traits,
  kind: saved.kind,
  saved: saved.id,
});

/** El guardado con ese nombre. Como en el backend, el nombre es la clave. */
export const savedNamed = (library: SavedCharacter[], name: string): SavedCharacter | undefined =>
  library.find((s) => fold(s.name) === fold(name));

/**
 * Cómo está un elemento del video respecto a la biblioteca: sin guardar,
 * guardado tal cual, o guardado con otros rasgos (guardarlo los pone al día).
 */
export function libraryState(character: Character, library: SavedCharacter[]): "unsaved" | "saved" | "changed" {
  const saved = savedNamed(library, character.name);
  if (!saved) return "unsaved";
  return fold(saved.traits) === fold(character.traits) && saved.kind === character.kind ? "saved" : "changed";
}

/** El reparto ya tiene un elemento con ese nombre. */
export const castHas = (cast: Character[], name: string): boolean =>
  cast.some((c) => fold(c.name) === fold(name));

/** Lo mete en el reparto, o pone al día el que ya tenga ese nombre. Con el reparto lleno, nada cambia. */
export function withCharacter(cast: Character[], character: Character): Character[] {
  const index = cast.findIndex((c) => fold(c.name) === fold(character.name));
  if (index >= 0) return cast.map((c, i) => (i === index ? character : c));
  return cast.length >= MAX_CHARACTERS ? cast : [...cast, character];
}

/**
 * Lo que se le propone a una escena: del reparto, lo que su descripción aún
 * no nombra; de la biblioteca, lo que aún no está en el reparto.
 */
export function suggestionsFor(
  description: string,
  cast: Character[],
  library: SavedCharacter[],
): Character[] {
  const named = new Set(castIn(description, cast).map((c) => fold(c.name)));
  const inCast = new Set(cast.map((c) => fold(c.name)));
  return [
    ...cast.filter((c) => c.name.trim() && !named.has(fold(c.name))),
    ...library.filter((s) => !inCast.has(fold(s.name))).map(fromSaved),
  ];
}

/** La descripción nombrando a ese elemento: es lo que hace que salga con sus rasgos y su referencia. */
export function mentioning(description: string, name: string): string {
  if (castIn(description, [{ ...blankCharacter(), name }]).length > 0) return description;
  const text = description.trim().replace(/[.\s]+$/, "");
  return text ? `${text}, con ${name}` : name;
}

/** Lo que llega del servidor en una lista de la biblioteca, con lo roto descartado. */
export function readSaved(items: unknown): SavedCharacter[] {
  if (!Array.isArray(items)) return [];
  return items.flatMap((raw) => {
    const item = raw as Partial<SavedCharacter> | null;
    if (!item || typeof item.id !== "number" || typeof item.name !== "string" || typeof item.traits !== "string") {
      return [];
    }
    return [{
      id: item.id,
      name: item.name,
      traits: item.traits,
      kind: isKind(item.kind) ? item.kind : "persona",
      reference: typeof item.reference === "string" ? item.reference : null,
      created_at: typeof item.created_at === "string" ? item.created_at : "",
      updated_at: typeof item.updated_at === "string" ? item.updated_at : "",
    }];
  });
}

