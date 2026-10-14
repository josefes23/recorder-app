import type { StudioGateway } from "@/application/ports";
import type { Style } from "@/domain/captions";
import type { Scene } from "@/domain/scene";
import { sampleCaption } from "@/domain/script";

export type PreviewInput = {
  script: string;
  topic: string;
  scenes: Scene[];
  style: Style;
};

/**
 * Un solo fotograma con el estilo aplicado: segundos en vez de los minutos que
 * cuesta el render, que es lo que hace usable el ajuste de subtítulos.
 */
export async function previewFrame(
  gateway: StudioGateway,
  { script, topic, scenes, style }: PreviewInput,
): Promise<Blob> {
  return gateway.previewFrame({
    caption: sampleCaption(script),
    topic,
    background: scenes[0]?.background ?? null,
    style,
  });
}
