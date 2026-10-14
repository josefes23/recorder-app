import type { StudioGateway } from "@/application/ports";
import type { Style } from "@/domain/captions";
import type { Scene } from "@/domain/scene";
import { canRender } from "@/domain/script";
import { formatPitch, formatRate } from "@/domain/voice";

export type RenderInput = {
  topic: string;
  script: string;
  voice: string;
  /** En crudo, como los mueve el deslizador: el formato lo pone el dominio. */
  rate: number;
  pitch: number;
  style: Style;
  scenes: Scene[];
};

/** Encola el render y devuelve el identificador del trabajo. */
export async function renderVideo(gateway: StudioGateway, input: RenderInput): Promise<number> {
  if (!canRender(input.script)) throw new Error("El guion está vacío.");

  return gateway.startRender({
    topic: input.topic.trim() || "Sin título",
    script: input.script,
    voice: input.voice,
    rate: formatRate(input.rate),
    pitch: formatPitch(input.pitch),
    style: input.style,
    scenes: input.scenes,
  });
}
