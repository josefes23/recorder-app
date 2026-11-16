import type { StudioGateway } from "@/application/ports";
import type { Style } from "@/domain/captions";
import { withoutLabels } from "@/domain/dialogue";
import type { FormatId } from "@/domain/production";
import type { Scene } from "@/domain/scene";
import { sampleCaption } from "@/domain/script";

export type PreviewInput = {
  script: string;
  topic: string;
  scenes: Scene[];
  style: Style;
  format?: FormatId;
};

/**
 * Un solo fotograma con el estilo aplicado: segundos en vez de los minutos que
 * cuesta el render, que es lo que hace usable el ajuste de subtítulos.
 */
export async function previewFrame(
  gateway: StudioGateway,
  { script, topic, scenes, style, format = "9:16" }: PreviewInput,
): Promise<Blob> {
  return gateway.previewFrame({
    // En un diálogo, el subtítulo de muestra no lleva «NARRADOR:»: la etiqueta no se oye.
    caption: sampleCaption(withoutLabels(script)),
    topic,
    background: scenes[0]?.background ?? null,
    style,
    format,
  });
}
