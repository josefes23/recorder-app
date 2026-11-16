import type { JobTracker, StudioGateway } from "@/application/ports";
import { readDescription } from "@/domain/description";

export type DescriptionInput = {
  topic: string;
  script: string;
  /** El de la portada: la descripción casa con él. */
  title: string;
};

/**
 * La descripción para publicar, escrita por el modelo del guion. Como el
 * guion, el servidor solo acusa recibo y el texto llega por el flujo de eventos.
 */
export async function writeDescription(
  gateway: StudioGateway,
  jobs: JobTracker,
  { topic, script, title }: DescriptionInput,
): Promise<string> {
  if (!script.trim()) throw new Error("Escribe primero el guion: la descripción lo resume.");
  const { job } = await gateway.requestDescription({ topic: topic.trim(), script, title });
  return readDescription(await jobs.waitFor(job));
}
