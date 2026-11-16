import type { JobTracker, StudioGateway } from "@/application/ports";
import { clipSeconds } from "@/domain/animation";
import type { VisualGuide } from "@/domain/illustration";
import type { FormatId } from "@/domain/production";

/**
 * Plantón para un clip animado. Generarlo tarda minutos y, con varias escenas,
 * espera turno detrás de otras (el servidor anima dos a la vez). El tope del
 * servidor por clip ronda los 22 minutos (HTTP_TIMEOUT, POLL_LIMIT y
 * DOWNLOAD_TIMEOUT en app/infrastructure/animation): esto queda por encima, para
 * que llegue el motivo real y no un «sin respuesta». No bloquea nada: el clip
 * se espera fuera de los botones, y si llega antes se resuelve antes.
 */
export const ANIMATION_GIVE_UP_MS = 60 * 60 * 1000;

export type AnimateInput = {
  topic: string;
  /** La guía del video: el estilo y el reparto ayudan a saber qué mover y cómo. */
  guide: VisualGuide;
  /** El clip sale con la orientación del video. */
  format?: FormatId;
};

export type SceneAnimation = {
  /** La imagen de la galería que se anima. */
  source: string;
  /** Qué pasa en la escena; puede ir vacío. */
  description: string;
  /** Cuánto dura su tramo, en segundos: el clip se pide de ese largo. */
  span: number;
};

/** Encola la animación de una imagen y devuelve el trabajo. */
export async function requestSceneAnimation(
  gateway: StudioGateway,
  { source, description, span }: SceneAnimation,
  { topic, guide, format = "9:16" }: AnimateInput,
): Promise<string> {
  if (!source) throw new Error("Esta escena no tiene imagen que animar.");
  const { job } = await gateway.requestAnimation({
    topic: topic.trim(),
    source,
    seconds: clipSeconds(span),
    description: description.trim(),
    look: guide.look.trim(),
    characters: guide.characters.filter((c) => c.name.trim() && c.traits.trim()),
    seed: guide.seed,
    format,
  });
  return job;
}

/** Espera el clip y devuelve su nombre en la galería. */
export async function awaitSceneClip(jobs: JobTracker, job: string): Promise<string> {
  const result = await jobs.waitFor(job, { giveUpMs: ANIMATION_GIVE_UP_MS });
  if (typeof result.name !== "string" || !result.name) {
    throw new Error("El clip llegó sin nombre. Vuelve a pedirlo.");
  }
  return result.name;
}
