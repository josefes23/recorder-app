import type { EventStream, StudioEvent } from "@/application/ports";

/** Espera antes de reintentar cuando se cae la conexión. */
const RETRY_MS = 1500;

/**
 * Adaptador del puerto `EventStream` sobre Server-Sent Events.
 *
 * SSE y no WebSocket porque el flujo es de una sola dirección: el servidor
 * cuenta lo que ha pasado.
 *
 * La reconexión la lleva este adaptador y no el navegador, a propósito.
 * `EventSource` reconecta por su cuenta, pero solo reenvía `Last-Event-ID` si
 * antes recibió un evento con `id` — y los latidos son comentarios que no lo
 * llevan. Con la reconexión automática, una caída durante el minuto largo que
 * tarda el modelo hacía que el servidor reanudara en la cabeza del log, y el
 * evento de fin publicado durante el hueco se perdía. Llevando aquí el último
 * offset entregado, se reanuda siempre en el punto exacto.
 */
export const sseEventStream: EventStream = {
  subscribe(onEvent: (event: StudioEvent) => void): () => void {
    let source: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let closed = false;
    let lastOffset: number | null = null;

    const open = () => {
      if (closed) return;

      // Sin `after` la primera vez: al abrir la pantalla solo interesa lo que
      // pase a partir de ahora, no el historial entero.
      source = new EventSource(
        lastOffset === null ? "/api/events" : `/api/events?after=${lastOffset}`,
      );

      // El servidor no nombra los eventos: el tema viaja dentro del JSON, así
      // que basta escuchar el mensaje por defecto sin conocer la lista de temas.
      source.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as StudioEvent;
          lastOffset = event.offset;
          onEvent(event);
        } catch {
          /* un evento ilegible no debe tumbar la suscripción */
        }
      };

      source.onerror = () => {
        source?.close();
        source = null;
        if (!closed) retry = setTimeout(open, RETRY_MS);
      };
    };

    open();

    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      source?.close();
    };
  },
};
