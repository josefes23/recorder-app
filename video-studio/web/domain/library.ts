import type { Style } from "./captions";
import { splitStoredStyle, type FormatId } from "./production.ts";
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
  /** La portada guardada con el render; se lee con `readCover`, vacía en los de antes. */
  cover?: unknown;
  /** El texto para publicar guardado con el render; vacío si no se escribió. */
  description?: string;
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

// --------------------------------------------------------------------------- //
// La biblioteca cuando crece: buscar, filtrar y enseñar por páginas
// --------------------------------------------------------------------------- //

export type StatusFilter = "all" | "done" | "failed" | "active";

export type LibraryFilter = {
  query: string;
  status: StatusFilter;
  format: FormatId | "all";
};

export const DEFAULT_FILTER: LibraryFilter = { query: "", status: "all", format: "all" };

/** Cuántos videos se enseñan de una vez: una pantalla de portadas, sin cargar cien. */
export const LIBRARY_PAGE = 12;

/** Sin tildes ni mayúsculas: «ayuno» encuentra «Ayunó». */
const fold = (text: string): string =>
  text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

/** El formato con que se hizo; los de antes de que hubiera formatos, verticales. */
export const videoFormat = (item: VideoItem): FormatId => splitStoredStyle(item.style).production.format;

export const statusOf = (item: VideoItem): Exclude<StatusFilter, "all"> =>
  item.status === "done" ? "done" : item.status === "error" ? "failed" : "active";

/**
 * Los videos que cumplen el filtro, en el mismo orden. La búsqueda mira el
 * tema, la descripción y el guion, y pide todas las palabras escritas.
 */
export function filterVideos(items: VideoItem[], filter: LibraryFilter): VideoItem[] {
  const words = fold(filter.query).split(/\s+/).filter(Boolean);
  return items.filter((item) => {
    if (filter.status !== "all" && statusOf(item) !== filter.status) return false;
    if (filter.format !== "all" && videoFormat(item) !== filter.format) return false;
    if (words.length === 0) return true;
    const haystack = fold(`${item.topic} ${item.description ?? ""} ${item.script}`);
    return words.every((word) => haystack.includes(word));
  });
}

export function countByStatus(items: VideoItem[]): Record<StatusFilter, number> {
  const counts: Record<StatusFilter, number> = { all: items.length, done: 0, failed: 0, active: 0 };
  for (const item of items) counts[statusOf(item)] += 1;
  return counts;
}

/** «0:43», «2:05»: como lo enseña cualquier reproductor. Vacío si no se sabe. */
export function clockTime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "";
  const total = Math.round(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/**
 * «hoy 16:38», «ayer 21:42», «12 nov», «3 mar 2025»: lo justo para ubicar un
 * video sin leer una marca de tiempo entera. `created_at` llega en hora local.
 */
export function dayLabel(createdAt: string, now: Date = new Date()): string {
  const when = new Date(createdAt.replace(" ", "T"));
  if (Number.isNaN(when.getTime())) return createdAt;
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((day(now) - day(when)) / 86_400_000);
  const time = `${when.getHours()}:${String(when.getMinutes()).padStart(2, "0")}`;
  if (days === 0) return `hoy ${time}`;
  if (days === 1) return `ayer ${time}`;
  const date = `${when.getDate()} ${MONTHS[when.getMonth()]}`;
  return when.getFullYear() === now.getFullYear() ? date : `${date} ${when.getFullYear()}`;
}
