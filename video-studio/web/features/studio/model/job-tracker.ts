"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";

import type { EventStream, JobTracker, StudioEvent } from "@/application/ports";
import { failureDetail, outcomeOf, type JobOutcome } from "@/domain/job";

/**
 * Convierte el flujo de eventos en promesas por trabajo.
 *
 * Qué evento cierra un trabajo lo decide el dominio (`outcomeOf`), así que
 * añadir tipos de trabajo nuevos no obliga a tocar esto.
 *
 * Hay dos vías hacia el mismo desenlace: el evento que empuja el servidor —la
 * rápida— y una consulta periódica al log. La segunda existe porque el empuje
 * depende de que la conexión esté viva en el instante exacto, y una pestaña
 * dormida o una reconexión a destiempo bastaban para perder el guion. El hecho
 * queda en el log, así que preguntar por él siempre lo recupera.
 */

/** Cada cuánto se pregunta por un trabajo cuyo evento no ha llegado. */
const POLL_MS = 4000;

/**
 * Red de seguridad para cuando el servidor muere de verdad: el botón no puede
 * quedarse «Escribiendo…» eternamente.
 *
 * Tiene que ser mayor que el tope del servidor (HTTP_TIMEOUT en scriptgen.py,
 * tres minutos), porque un trabajo lento siempre acaba publicando su fallo con
 * el motivo bueno. Si empatan, gana este mensaje genérico y se pierde el útil.
 */
const GIVE_UP_MS = 5 * 60 * 1000;

type Pending = {
  resolve: (payload: Record<string, unknown>) => void;
  reject: (error: Error) => void;
  /** Suelta el temporizador y la consulta periódica de este trabajo. */
  dispose: () => void;
};

export function useJobTracker(
  events: EventStream,
  jobStatus: (job: string) => Promise<Record<string, unknown>>,
): JobTracker {
  const pending = useRef(new Map<string, Pending>());

  const finish = useCallback(
    (job: string, outcome: JobOutcome, payload: Record<string, unknown>) => {
      if (outcome === "pending") return;

      // Puede ser de otra pestaña o de una sesión anterior: el log lo cuenta
      // todo, y aquí solo interesan los trabajos que esta pantalla espera.
      const entry = pending.current.get(job);
      if (!entry) return;

      pending.current.delete(job);
      entry.dispose();

      if (outcome === "failed") {
        entry.reject(new Error(failureDetail(payload)));
        return;
      }
      entry.resolve(payload);
    },
    [],
  );

  const settle = useCallback(
    (event: StudioEvent) => {
      if (!event.key) return;
      finish(event.key, outcomeOf(event.topic), event.payload);
    },
    [finish],
  );

  useEffect(() => {
    const unsubscribe = events.subscribe(settle);
    const waiting = pending.current;
    return () => {
      unsubscribe();
      // Al desmontar se pierde la escucha, así que los trabajos en vuelo se
      // rechazan ya en lugar de dejar la promesa huérfana hasta el plantón de
      // cinco minutos. Pasa con la recarga en caliente de desarrollo.
      waiting.forEach((entry) => {
        entry.dispose();
        entry.reject(new Error("Se cortó la escucha de eventos. Vuelve a intentarlo."));
      });
      waiting.clear();
    };
  }, [events, settle]);

  const waitFor = useCallback(
    (job: string) =>
      new Promise<Record<string, unknown>>((resolve, reject) => {
        const poller = setInterval(async () => {
          try {
            const state = await jobStatus(job);
            const status = typeof state.status === "string" ? state.status : "pending";
            if (status === "pending") return;
            finish(job, status === "failed" ? "failed" : "completed", state);
          } catch {
            /* un fallo puntual de red se reintenta en el siguiente tick */
          }
        }, POLL_MS);

        const timer = setTimeout(() => {
          const entry = pending.current.get(job);
          pending.current.delete(job);
          entry?.dispose();
          reject(new Error("El servidor no ha contestado en cinco minutos. Revisa que siga en marcha."));
        }, GIVE_UP_MS);

        pending.current.set(job, {
          resolve,
          reject,
          dispose: () => {
            clearTimeout(timer);
            clearInterval(poller);
          },
        });
      }),
    [finish, jobStatus],
  );

  return useMemo(() => ({ waitFor }), [waitFor]);
}
