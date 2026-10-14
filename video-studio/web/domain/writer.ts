/** Quién redacta el guion: proveedor, clave y modelo. */

export type WriterModel = { id: string; label: string; group: string };

export type WriterProvider = {
  id: string;
  name: string;
  note: string;
  /** Variable del .env donde se guarda la clave. */
  key_env: string;
  /** Últimos caracteres de la clave guardada, o null si no hay ninguna. */
  key_hint: string | null;
  model: string;
  models: WriterModel[];
};

export type Writer = {
  provider: string;
  /** Etiqueta corta del modelo activo, o null si falta la clave. */
  label: string | null;
  providers: WriterProvider[];
};

export type WriterDraft = {
  provider: string;
  /** Vacía significa «conserva la que ya estaba guardada». */
  api_key: string;
  model: string;
};

export const providerOf = (writer: Writer, id: string): WriterProvider =>
  writer.providers.find((p) => p.id === id) ?? writer.providers[0];

/** Sin clave guardada ni escrita no hay nada que activar. */
export const canSave = (provider: WriterProvider, typedKey: string): boolean =>
  Boolean(provider.key_hint) || typedKey.trim().length > 0;

export const modelGroups = (provider: WriterProvider): string[] => [
  ...new Set(provider.models.map((m) => m.group)),
];
