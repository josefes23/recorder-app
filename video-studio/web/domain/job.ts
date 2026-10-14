/**
 * Convención del log de eventos para los trabajos encolados.
 *
 * Un tema terminado en `.completed` cierra el trabajo con éxito y uno en
 * `.failed` lo cierra con error; el resto —`.requested` y cualquier evento de
 * progreso que se añada— son intermedios. Vive aquí, y no en el hook que
 * escucha, porque es una regla del dominio: cambiarla afecta al backend y al
 * front por igual, y así se puede probar sin navegador.
 */

export type JobOutcome = "completed" | "failed" | "pending";

export function outcomeOf(topic: string): JobOutcome {
  if (topic.endsWith(".completed")) return "completed";
  if (topic.endsWith(".failed")) return "failed";
  return "pending";
}

/** Mensaje del fallo, ya listo para enseñar, o uno genérico si no vino. */
export function failureDetail(payload: Record<string, unknown>): string {
  const detail = payload.detail;
  return typeof detail === "string" && detail.trim() ? detail : "El trabajo falló.";
}
