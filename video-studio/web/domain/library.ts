import type { Style } from "./captions";
import type { Scene } from "./scene";

export type VideoStatus = "queued" | "running" | "done" | "error";

export type VideoItem = {
  id: number;
  topic: string;
  script: string;
  voice: string;
  style: Partial<Style>;
  scenes: Scene[];
  filename: string | null;
  duration: number | null;
  size_mb: number | null;
  captions: number | null;
  status: VideoStatus;
  error: string | null;
  created_at: string;
  /* Presentes solo mientras el trabajo sigue en la cola en memoria. */
  progress?: number;
  message?: string;
  phase?: string;
};

/**
 * Un trabajo en curso: lo mínimo que la cola sabe de él mientras se renderiza,
 * antes de que exista la ficha completa del video.
 */
export type JobStatus = Pick<VideoItem, "id" | "status"> &
  Partial<Pick<VideoItem, "progress" | "message" | "error">>;

/** Tiene archivo que reproducir y descargar. */
export const isPlayable = (item: VideoItem): boolean =>
  item.status === "done" && Boolean(item.filename);

/** Ya no va a cambiar: se puede dejar de preguntar por él. */
export const isSettled = (job: { status: VideoStatus }): boolean =>
  job.status === "done" || job.status === "error";

export const isRendering = (job: JobStatus | null): boolean =>
  job !== null && !isSettled(job);
