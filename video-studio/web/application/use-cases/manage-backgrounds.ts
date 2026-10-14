import type { StudioGateway } from "@/application/ports";
import type { Background } from "@/domain/background";

/**
 * Descarga y subida devuelven ya la galería entera actualizada, así que no hace
 * falta volver a pedirla después.
 */

export async function downloadBackgrounds(
  gateway: StudioGateway,
  query: string,
): Promise<{ log: string; items: Background[] }> {
  const search = query.trim();
  if (!search) throw new Error("Escribe qué clips buscar.");
  return gateway.fetchBackgrounds(search);
}

export const uploadBackground = (gateway: StudioGateway, file: File): Promise<Background[]> =>
  gateway.uploadBackground(file);

export const listBackgrounds = (gateway: StudioGateway): Promise<Background[]> =>
  gateway.backgrounds();
