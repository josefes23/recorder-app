import type { StudioGateway } from "@/application/ports";
import { canSave, providerOf, type Writer, type WriterDraft } from "@/domain/writer";

/**
 * Guarda proveedor, clave y modelo. La clave viaja una sola vez: el servidor la
 * escribe en el .env y solo devuelve sus últimos caracteres.
 */
export async function configureWriter(
  gateway: StudioGateway,
  current: Writer,
  draft: WriterDraft,
): Promise<Writer> {
  if (!canSave(providerOf(current, draft.provider), draft.api_key)) {
    throw new Error("Pega la clave de API antes de guardar.");
  }
  return gateway.saveWriter({ ...draft, api_key: draft.api_key.trim() });
}
