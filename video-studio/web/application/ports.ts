import type { Background } from "@/domain/background";
import type { Style } from "@/domain/captions";
import type { Config } from "@/domain/config";
import type { VideoItem } from "@/domain/library";
import type { Scene } from "@/domain/scene";
import type { Writer, WriterDraft } from "@/domain/writer";

export type ScriptDraft = { script: string; seconds: number };

/** Acuse de recibo de un encargo: el resultado llegará por el flujo de eventos. */
export type JobAccepted = { job: string; offset: number };

export type StudioEvent = {
  /** Posición en el log. Sirve para reanudar tras un corte. */
  offset: number;
  topic: string;
  /** Clave del trabajo al que pertenece el evento. */
  key: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

/**
 * Puerto de entrada: hechos que el servidor empuja según ocurren.
 *
 * Separado del gateway a propósito — uno es petición/respuesta y el otro es un
 * flujo. Hoy lo implementa SSE; cambiarlo por WebSocket o por un broker real es
 * reescribir el adaptador y nada más.
 */
export interface EventStream {
  /** Escucha desde ahora. Devuelve la función que corta la suscripción. */
  subscribe(onEvent: (event: StudioEvent) => void): () => void;
}

/** Espera el desenlace de un trabajo encolado. */
export interface JobTracker {
  waitFor(job: string): Promise<Record<string, unknown>>;
}

export type PreviewRequest = {
  caption: string;
  topic: string;
  background: string | null;
  style: Style;
};

export type RenderRequest = {
  topic: string;
  script: string;
  voice: string;
  /** Ya formateados para el motor: «+8%», «-4Hz». */
  rate: string;
  pitch: string;
  style: Style;
  scenes: Scene[];
};

/**
 * Puerto de salida: todo lo que la aplicación necesita del mundo exterior.
 *
 * Los casos de uso hablan con esta interfaz y nunca con `fetch`, así que
 * cambiar de transporte —o falsearlo en una prueba— es cambiar de
 * implementación, no tocar la lógica. La implementación vive en
 * `infrastructure/` y se inyecta desde la ruta.
 */
export interface StudioGateway {
  config(): Promise<Config>;

  writer(): Promise<Writer>;
  saveWriter(draft: WriterDraft): Promise<Writer>;

  /** Encola la redacción; contesta al instante con la clave del trabajo. */
  requestScript(topic: string, notes: string): Promise<JobAccepted>;
  /** Desenlace de un trabajo: la red de seguridad si su evento no llegó. */
  jobStatus(job: string): Promise<Record<string, unknown>>;
  /** La plantilla es local: se resuelve en la misma petición. */
  templateScript(topic: string): Promise<ScriptDraft>;

  backgrounds(): Promise<Background[]>;
  fetchBackgrounds(query: string, count?: number): Promise<{ log: string; items: Background[] }>;
  uploadBackground(file: File): Promise<Background[]>;

  previewFrame(request: PreviewRequest): Promise<Blob>;

  startRender(request: RenderRequest): Promise<number>;
  job(id: number): Promise<VideoItem>;

  videos(): Promise<VideoItem[]>;
  deleteVideo(id: number): Promise<void>;

  /** URLs que sirve el propio backend; la interfaz no arma rutas a mano. */
  thumbUrl(thumb: string | null): string;
  videoUrl(id: number): string;
}
