import type { StudioGateway } from "@/application/ports";
import {
  canSaveImages,
  imageProviderOf,
  type ImageSettings,
  type ImageSettingsDraft,
} from "@/domain/illustration";

/**
 * Guarda generador, modelo y datos. Las claves viajan una sola vez: el
 * servidor las escribe en el .env y solo devuelve sus últimos caracteres.
 */
export async function configureImages(
  gateway: StudioGateway,
  current: ImageSettings,
  draft: ImageSettingsDraft,
): Promise<ImageSettings> {
  if (!canSaveImages(imageProviderOf(current, draft.provider), draft.values)) {
    throw new Error("Rellena los datos del generador antes de guardar.");
  }
  const values = Object.fromEntries(
    Object.entries(draft.values)
      .map(([env, value]) => [env, value.trim()] as const)
      .filter(([, value]) => value.length > 0),
  );
  return gateway.saveImageSettings({ ...draft, values });
}
