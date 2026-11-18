import type { GrowthRequest, JobTracker, StudioGateway } from "@/application/ports";
import { growthBlocker, readGrowth, type GrowthKind, type GrowthResults } from "@/domain/growth";

/**
 * Un consejo de crecimiento, escrito por el modelo del guion. Como el guion,
 * el servidor solo acusa recibo y el consejo llega por el flujo de eventos.
 */
export async function askGrowth<K extends GrowthKind>(
  gateway: StudioGateway,
  jobs: JobTracker,
  kind: K,
  request: GrowthRequest,
): Promise<GrowthResults[K]> {
  const blocker = growthBlocker(kind, request.topic, request.script);
  if (blocker) throw new Error(blocker);
  const { job } = await gateway.requestGrowth(kind, {
    ...request,
    topic: request.topic.trim(),
    description: request.description.trim(),
  });
  return readGrowth(kind, await jobs.waitFor(job));
}
