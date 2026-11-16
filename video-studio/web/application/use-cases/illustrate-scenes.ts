import type { IllustrationRequest, JobTracker, StudioGateway } from "@/application/ports";
import {
  isKind,
  readReview,
  type Character,
  type ImageChoice,
  type ImageReview,
  type Storyboard,
  type StoryboardScene,
  type VisualGuide,
} from "@/domain/illustration";

export type IllustrateInput = ImageChoice & {
  topic: string;
  /** Estilo, reparto y semilla comunes a todas las escenas, para que casen entre sí. */
  guide: VisualGuide;
  /** Que el modelo del guion revise cada imagen y repinte las que tengan fallos. */
  review: boolean;
};

/** Una imagen terminada: su nombre en la galería y lo que dijo el revisor. */
export type SceneImage = { name: string; review: ImageReview | null };

export type StoryboardInput = {
  topic: string;
  script: string;
  style: string;
  /** El reparto que ya está en el video: el guion visual lo incluye entero. */
  characters: Character[];
};

const request = (input: IllustrateInput, description: string): IllustrationRequest => ({
  topic: input.topic.trim(),
  description,
  look: input.guide.look.trim(),
  characters: input.guide.characters,
  seed: input.guide.seed,
  provider: input.provider,
  model: input.model,
  review: input.review,
});

const isText = (value: unknown): value is string => typeof value === "string";

/**
 * Comprueba la forma de lo que llegó por el flujo de eventos. El servidor ya
 * lo validó; esto solo protege de un contrato roto, que de otro modo
 * reventaría más tarde y lejos de aquí.
 */
export function readStoryboard(result: Record<string, unknown>): Storyboard {
  const guide = result.guide as Partial<VisualGuide> | undefined;
  const scenes = result.scenes as Partial<StoryboardScene>[] | undefined;
  if (!guide || !isText(guide.look) || !Array.isArray(scenes) || scenes.length === 0) {
    throw new Error("El guion visual llegó vacío. Vuelve a intentarlo.");
  }
  return {
    guide: {
      look: guide.look,
      characters: (Array.isArray(guide.characters) ? guide.characters : []).flatMap((raw) => {
        const c = raw as Partial<Character> | null;
        if (!isText(c?.name) || !isText(c?.traits)) return [];
        return [{
          name: c.name,
          traits: c.traits,
          kind: isKind(c.kind) ? c.kind : "persona",
          saved: typeof c.saved === "number" ? c.saved : null,
        }];
      }),
      seed: typeof guide.seed === "number" ? guide.seed : null,
    },
    scenes: scenes.map((scene) => ({
      start: typeof scene.start === "number" ? scene.start : 0,
      text: isText(scene.text) ? scene.text : "",
      description: isText(scene.description) ? scene.description : "",
    })),
  };
}

/**
 * El modelo del guion decide qué se ve en cada escena, quién sale y con qué
 * estilo. Tarda como redactar un guion, así que llega por el flujo de eventos.
 */
export async function planStoryboard(
  gateway: StudioGateway,
  jobs: JobTracker,
  { topic, script, style, characters }: StoryboardInput,
): Promise<Storyboard> {
  if (!script.trim()) throw new Error("Escribe primero el guion: las escenas salen de sus frases.");
  const { job } = await gateway.requestStoryboard({
    topic: topic.trim(),
    script,
    style: style.trim(),
    // Las filas a medio rellenar no viajan: el servidor las rechazaría.
    characters: characters.filter((c) => c.name.trim() && c.traits.trim()),
  });
  return readStoryboard(await jobs.waitFor(job));
}

/**
 * Pide una imagen por escena con la misma guía. `onRequested` avisa de cada
 * encargo según sale, para que su escena lo espere.
 *
 * Los encargos salen uno a uno y no a la vez: si el primero se rechaza —sin
 * clave, generador desconocido— no queda media docena encolada por detrás.
 */
export async function requestSceneImages(
  gateway: StudioGateway,
  descriptions: string[],
  input: IllustrateInput,
  onRequested: (index: number, job: string) => void,
): Promise<void> {
  for (const [index, description] of descriptions.entries()) {
    const { job } = await gateway.requestIllustration(request(input, description.trim()));
    onRequested(index, job);
  }
}

/** Pide una sola imagen con la descripción que haya escrito el usuario. */
export async function requestSceneImage(
  gateway: StudioGateway,
  description: string,
  input: IllustrateInput,
): Promise<string> {
  const text = description.trim();
  if (!text) throw new Error("Describe qué debe mostrar la imagen.");
  const { job } = await gateway.requestIllustration(request(input, text));
  return job;
}

export type CorrectionInput = {
  /** La imagen de la galería que se corrige. */
  source: string;
  /** Qué está mal, contado por el usuario. */
  correction: string;
  /** Lo que debía mostrar, si se sabe: ayuda al generador y al revisor. */
  description: string;
};

/**
 * Pide corregir una imagen: el generador parte de ella y cambia solo lo que se
 * le dice. La corregida llega como cualquier otra imagen y con nombre propio;
 * la original se queda en la galería.
 */
export async function requestSceneCorrection(
  gateway: StudioGateway,
  { source, correction, description }: CorrectionInput,
  input: IllustrateInput,
): Promise<string> {
  const text = correction.trim();
  if (!source) throw new Error("Esta escena no tiene imagen que corregir.");
  if (!text) throw new Error("Cuenta qué está mal en la imagen para que la IA lo corrija.");
  const { job } = await gateway.requestIllustration({
    ...request(input, description.trim()),
    source,
    correction: text,
  });
  return job;
}

/** Espera la imagen y devuelve su nombre en la galería y su revisión. */
export async function awaitSceneImage(jobs: JobTracker, job: string): Promise<SceneImage> {
  const result = await jobs.waitFor(job);
  if (typeof result.name !== "string" || !result.name) {
    throw new Error("La imagen llegó sin nombre. Vuelve a pedirla.");
  }
  return { name: result.name, review: readReview(result.review) };
}
