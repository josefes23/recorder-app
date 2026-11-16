import type { CoverRequest, JobTracker, StudioGateway } from "@/application/ports";
import { readTitles } from "@/domain/cover";

/** La portada a tamaño completo: pintarla es local y tarda menos de un segundo. */
export async function paintCover(gateway: StudioGateway, request: CoverRequest): Promise<Blob> {
  return gateway.coverImage({ ...request, topic: request.topic.trim() });
}

export type TitlesInput = { topic: string; script: string };

/**
 * Títulos gancho escritos por el modelo del guion. Como el guion, el servidor
 * solo acusa recibo y los títulos llegan por el flujo de eventos.
 */
export async function suggestTitles(
  gateway: StudioGateway,
  jobs: JobTracker,
  { topic, script }: TitlesInput,
): Promise<string[]> {
  if (!topic.trim() && !script.trim()) throw new Error("Escribe primero el tema o el guion.");
  const { job } = await gateway.requestTitles(topic.trim(), script);
  return readTitles(await jobs.waitFor(job));
}
