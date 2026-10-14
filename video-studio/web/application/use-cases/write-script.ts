import type { JobTracker, StudioGateway } from "@/application/ports";

export type WriteScriptInput = {
  topic: string;
  notes: string;
  /** Plantilla local del motor en vez del modelo: no gasta API ni tarda. */
  useTemplate: boolean;
};

export async function writeScript(
  gateway: StudioGateway,
  jobs: JobTracker,
  { topic, notes, useTemplate }: WriteScriptInput,
): Promise<string> {
  const subject = topic.trim();
  if (!subject) throw new Error("Escribe primero un tema.");

  if (useTemplate) return (await gateway.templateScript(subject)).script;

  /* El servidor solo acusa recibo del encargo; el guion llega por el flujo de
     eventos cuando el modelo termina, que puede ser un minuto después. */
  const { job } = await gateway.requestScript(subject, notes);
  const result = await jobs.waitFor(job);

  const script = result.script;
  if (typeof script !== "string" || !script.trim()) {
    throw new Error("El guion llegó vacío. Vuelve a intentarlo.");
  }
  return script;
}
