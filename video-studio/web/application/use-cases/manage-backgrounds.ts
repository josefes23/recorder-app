import type { StudioGateway } from "@/application/ports";
import type { Background } from "@/domain/background";
import type { FormatId } from "@/domain/production";
import type { DownloadReport, StockSearch } from "@/domain/stock";

/**
 * Buscar no descarga nada: devuelve miniaturas para que el usuario marque qué
 * quiere. Descargar, subir y borrar devuelven ya la galería entera
 * actualizada, así que no hace falta volver a pedirla después.
 */

/** Los clips salen con la orientación del video: verticales para reels, horizontales para YouTube. */
export async function searchStock(
  gateway: StudioGateway,
  query: string,
  format: FormatId = "9:16",
): Promise<StockSearch> {
  const search = query.trim();
  if (!search) throw new Error("Escribe qué clips buscar.");
  return { query: search, clips: await gateway.searchStock(search, format) };
}

export async function downloadStock(
  gateway: StudioGateway,
  query: string,
  ids: number[],
  format: FormatId = "9:16",
): Promise<DownloadReport & { items: Background[] }> {
  if (ids.length === 0) throw new Error("Marca al menos un clip para descargar.");
  return gateway.downloadStock(query, ids, format);
}

export const uploadBackground = (gateway: StudioGateway, file: File): Promise<Background[]> =>
  gateway.uploadBackground(file);

export const deleteBackground = (gateway: StudioGateway, name: string): Promise<Background[]> =>
  gateway.deleteBackground(name);

export const listBackgrounds = (gateway: StudioGateway): Promise<Background[]> =>
  gateway.backgrounds();
