import type { StudioGateway } from "@/application/ports";
import type { VideoItem } from "@/domain/library";

export const listVideos = (gateway: StudioGateway): Promise<VideoItem[]> => gateway.videos();

/** Borrar deja la lista obsoleta, así que se devuelve ya recargada. */
export async function deleteVideo(gateway: StudioGateway, id: number): Promise<VideoItem[]> {
  await gateway.deleteVideo(id);
  return gateway.videos();
}
