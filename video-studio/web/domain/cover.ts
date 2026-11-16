import { isImageFile as isImage } from "./background.ts";
import type { Scene } from "./scene";

/**
 * La portada: un título gancho en grande sobre una imagen. Lo que va entre
 * asteriscos sale resaltado en otro color.
 *
 * Los diseños y la regla del título por defecto son los de
 * `app/domain/cover.py`: cambiarlos aquí sin cambiarlos allí da un 400.
 */

export type CoverDesign = "impacto" | "franja" | "titular";

export const COVER_DESIGNS: { id: CoverDesign; label: string; hint: string }[] = [
  { id: "impacto", label: "Impacto", hint: "Texto gigante abajo, la palabra clave en amarillo" },
  { id: "franja", label: "Franja", hint: "Cada línea sobre una franja amarilla, abajo" },
  { id: "titular", label: "Titular", hint: "Arriba, con la palabra clave en una caja roja" },
];

export const DEFAULT_DESIGN: CoverDesign = "impacto";

/** Más de esto ya no se lee en una miniatura. El servidor admite hasta doce. */
export const IDEAL_TITLE_WORDS = 6;

export type Cover = {
  title: string;
  design: CoverDesign;
  /** Nombre en la galería; null pinta el degradado del tema. */
  background: string | null;
};

const isDesign = (value: unknown): value is CoverDesign =>
  COVER_DESIGNS.some((design) => design.id === value);

export const plainTitle = (title: string): string => title.replaceAll("*", " ").split(/\s+/).filter(Boolean).join(" ");

export const titleWords = (title: string): number => plainTitle(title).split(" ").filter(Boolean).length;

const bare = (word: string) => word.replace(/[¿?¡!,;:]/g, "");

/** El tema con su palabra más larga resaltada: la portada que sale sin pedir nada al modelo. */
export function defaultTitle(topic: string): string {
  const title = topic.split(/\s+/).filter(Boolean).join(" ").replace(/^["'«»“”‘’`]+|["'«»“”‘’`.]+$/g, "");
  if (!title || title.includes("*")) return title;
  const words = title.split(" ");
  let longest = 0;
  words.forEach((word, i) => {
    if (bare(word).length > bare(words[longest]).length) longest = i;
  });
  if (bare(words[longest]).length < 4) return title;
  words[longest] = `*${words[longest]}*`;
  return words.join(" ");
}

/**
 * Las palabras del título, cada una sabiendo si va resaltada: para pintar las
 * sugerencias. Misma regla que `cover_words` del servidor: se trocea por
 * espacios, así que en «*Padre*, no» la coma va con su palabra.
 */
export function titleParts(title: string): { text: string; highlighted: boolean }[] {
  let text = title;
  if ((text.match(/\*/g) ?? []).length % 2) {
    const cut = text.lastIndexOf("*");
    text = text.slice(0, cut) + text.slice(cut + 1);
  }
  let inside = false;
  return text.split(/\s+/).flatMap((token) => {
    let letters = "";
    let highlighted = false;
    for (const char of token) {
      if (char === "*") {
        inside = !inside;
        continue;
      }
      letters += char;
      highlighted ||= inside;
    }
    return letters ? [{ text: letters, highlighted }] : [];
  });
}

/**
 * Las imágenes de las escenas, sin repetir y en orden: entre ellas se elige la
 * de la portada. Una escena animada aporta su imagen fija antes que su clip:
 * la portada sale mejor de la imagen entera que de un fotograma del video.
 */
export function coverCandidates(scenes: Scene[]): string[] {
  const names = scenes.flatMap((scene) =>
    [scene.still, scene.background].filter((name): name is string => Boolean(name)),
  );
  return [...new Set(names)];
}

/**
 * La que usa la portada si nadie elige otra: la primera escena con imagen —las
 * generadas ponen las caras arriba—, o el primer clip si no hay ninguna.
 */
export function firstBackground(scenes: Scene[]): string | null {
  const names = coverCandidates(scenes);
  return names.find(isImage) ?? names[0] ?? null;
}

/**
 * Lo que el usuario eligió, con `null` para «automático»: el título sigue al
 * tema y la imagen a la primera escena hasta que se toquen.
 */
export type CoverDraft = { title: string | null; design: CoverDesign; background: string | null };

/**
 * La portada que sale con el borrador y el tema de ahora; null si no hay título.
 * `automatic` es la imagen de `firstBackground`: llega ya calculada para que
 * quien la use dependa de un nombre y no de la lista entera de escenas, que
 * cambia cada vez que una imagen pedida avanza.
 */
export function resolveCover(draft: CoverDraft, topic: string, automatic: string | null): Cover | null {
  const title = draft.title ?? defaultTitle(topic);
  if (!plainTitle(title)) return null;
  return { title, design: draft.design, background: draft.background ?? automatic };
}

/**
 * El encargo de partida para pintar una imagen solo para la portada. Lo que
 * para el dedo es una cara con emoción y mucho contraste; el usuario lo retoca
 * antes de pedirla.
 */
export function coverImagePrompt(topic: string, scenePrompt?: string): string {
  const subject = topic.trim() ? ` sobre «${topic.trim()}»` : "";
  const scene = scenePrompt?.trim() ? ` ${scenePrompt.trim().replace(/\.?$/, ".")}` : "";
  return (
    `Imagen de portada para un video corto${subject}.${scene} Primer plano expresivo, ` +
    "con una emoción intensa en la cara, colores vivos, mucho contraste y un fondo sencillo."
  );
}

/** La portada que se guardó con un video, o null si es de antes de que las hubiera. */
export function readCover(raw: unknown): Cover | null {
  const cover = raw as Partial<Cover> | null | undefined;
  if (!cover || typeof cover.title !== "string" || !plainTitle(cover.title)) return null;
  return {
    title: cover.title,
    design: isDesign(cover.design) ? cover.design : DEFAULT_DESIGN,
    background: typeof cover.background === "string" && cover.background ? cover.background : null,
  };
}

/** Comprueba la forma de los títulos que llegaron por el flujo de eventos. */
export function readTitles(result: Record<string, unknown>): string[] {
  const titles = Array.isArray(result.titles)
    ? result.titles.filter((t): t is string => typeof t === "string" && Boolean(plainTitle(t)))
    : [];
  if (!titles.length) throw new Error("El modelo no propuso títulos. Vuelve a intentarlo.");
  return titles;
}

/** Igual que `slugify` del servidor, para que el archivo se llame igual se baje de donde se baje. */
export function coverFilename(topic: string): string {
  const slug = topic.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
  return `portada-${slug || "video"}.jpg`;
}
