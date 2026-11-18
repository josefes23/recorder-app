/**
 * Dónde se enseña cada error: junto al paso o al panel cuya acción lo dio, no
 * al fondo del panel de salida, lejos del botón que se pulsó. Toda clave cae
 * en algún sitio; lo que no se reconoce (la carga inicial, el render) va a la
 * salida, así que ningún error se pierde ni sale dos veces.
 */
export type ErrorPlace = "script" | "sound" | "scenes" | "picker" | "cover" | "description" | "output";

const PREFIXES: [string, ErrorPlace][] = [
  ["writer", "script"],
  ["template", "script"],
  ["music", "sound"],
  ["storyboard", "scenes"],
  ["illustrate", "scenes"],
  ["correct", "scenes"],
  ["animate", "scenes"],
  ["save-character", "scenes"],
  ["reference", "scenes"],
  ["characters", "scenes"],
  ["images", "scenes"],
  ["search", "picker"],
  ["backgrounds", "picker"],
  ["titles", "cover"],
  ["cover", "cover"],
  ["description", "description"],
];

export function errorPlace(key: string | null): ErrorPlace {
  if (!key) return "output";
  const found = PREFIXES.find(([prefix]) => key === prefix || key.startsWith(`${prefix}-`));
  return found ? found[1] : "output";
}
