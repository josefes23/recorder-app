/**
 * Los prompts que el estudio manda por debajo, tal como los devuelve el
 * servidor (`app/domain/prompts.py`): el texto actual con sus variables, el
 * original y un ejemplo ya montado con datos de muestra.
 */
export type PromptGroup = "texto" | "imagen" | "video";

export type PromptVariable = { name: string; help: string };

export type PromptExample = { label: string; text: string };

export type PromptInfo = {
  id: string;
  name: string;
  group: PromptGroup;
  /** Cuándo se manda. */
  when: string;
  /** Qué datos van aparte, como mensaje del usuario (no se editan). */
  user_part: string;
  variables: PromptVariable[];
  default: string;
  /** El texto en uso: el editado, o el original. */
  text: string;
  edited: boolean;
  examples: PromptExample[];
  warnings: string[];
};

export type PromptPreview = { examples: PromptExample[]; warnings: string[] };

export const GROUP_LABELS: Record<PromptGroup, string> = {
  texto: "Modelo de texto",
  imagen: "Generador de imágenes",
  video: "Generador de video",
};

/** Agrupa por modelo, en el orden de GROUP_LABELS. */
export function byGroup(prompts: PromptInfo[]): { group: PromptGroup; items: PromptInfo[] }[] {
  return (Object.keys(GROUP_LABELS) as PromptGroup[])
    .map((group) => ({ group, items: prompts.filter((p) => p.group === group) }))
    .filter((entry) => entry.items.length > 0);
}

/** Cuántos están editados, para el aviso de la barra. */
export const editedCount = (prompts: PromptInfo[]): number => prompts.filter((p) => p.edited).length;
