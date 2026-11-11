import type { JobTracker, StudioGateway } from "@/application/ports";
import { readReview, type Character, type ImageChoice, type ImageReview } from "@/domain/illustration";

/** Una imagen de referencia terminada: su archivo y lo que dijo el revisor. */
export type ReferenceImage = { reference: string; review: ImageReview | null };

/**
 * Guarda un elemento del video en la biblioteca. Queda guardado al momento;
 * su imagen de referencia (`job`) llega por el flujo de eventos, o es null si
 * la que ya tenía sigue valiendo.
 */
export async function saveToLibrary(
  gateway: StudioGateway,
  character: Character,
  look: string,
  choice: ImageChoice | null,
) {
  if (!character.name.trim() || !character.traits.trim()) {
    throw new Error("Ponle nombre y rasgos antes de guardarlo.");
  }
  return gateway.saveCharacter({
    name: character.name.trim(),
    traits: character.traits.trim(),
    kind: character.kind,
    look: look.trim(),
    provider: choice?.provider ?? "",
    model: choice?.model ?? "",
  });
}

/** Pide otra imagen de referencia, con el estilo del video que esté abierto. */
export async function repaintReference(
  gateway: StudioGateway,
  id: number,
  look: string,
  choice: ImageChoice | null,
): Promise<string> {
  const { job } = await gateway.repaintReference(id, {
    look: look.trim(),
    provider: choice?.provider ?? "",
    model: choice?.model ?? "",
  });
  return job;
}

export async function awaitReference(jobs: JobTracker, job: string): Promise<ReferenceImage> {
  const result = await jobs.waitFor(job);
  if (typeof result.reference !== "string" || !result.reference) {
    throw new Error("La imagen de referencia llegó vacía. Vuelve a pedirla.");
  }
  return { reference: result.reference, review: readReview(result.review) };
}
