/**
 * La descripción con la que se publica el video: lo que leen los buscadores.
 * El tope es el de YouTube, como en `app/domain/description.py`.
 */

export const DESCRIPTION_LIMIT = 5000;

/** Dónde cortan las otras plataformas: pasarse se avisa, no se impide. */
const PLATFORM_CUTS = [
  { chars: 4000, warning: "TikTok la corta a 4000 caracteres e Instagram a 2200." },
  { chars: 2200, warning: "Instagram la corta a 2200 caracteres; YouTube y TikTok la admiten entera." },
] as const;

/**
 * Lo que se lee antes de «más» en el feed y en los resultados de búsqueda,
 * unas 125 letras en Instagram y YouTube. Ahí tienen que estar las palabras clave.
 */
export const VISIBLE_CHARS = 125;

export const descriptionLength = (text: string): number => text.trim().length;

/** Aviso si alguna plataforma la va a cortar; null si cabe en todas. */
export function platformWarning(text: string): string | null {
  const length = descriptionLength(text);
  return PLATFORM_CUTS.find((cut) => length > cut.chars)?.warning ?? null;
}

/** El principio que se ve sin desplegar, cortado por la última palabra entera. */
export function visiblePart(text: string): string {
  const flat = text.trim().split(/\s+/).filter(Boolean).join(" ");
  if (flat.length <= VISIBLE_CHARS) return flat;
  const cut = flat.slice(0, VISIBLE_CHARS);
  const space = cut.lastIndexOf(" ");
  return `${space > 0 ? cut.slice(0, space) : cut}…`;
}

/** Comprueba la forma de la descripción que llegó por el flujo de eventos. */
export function readDescription(result: Record<string, unknown>): string {
  const text = result.description;
  if (typeof text !== "string" || !text.trim()) {
    throw new Error("La descripción llegó vacía. Vuelve a intentarlo.");
  }
  return text;
}
