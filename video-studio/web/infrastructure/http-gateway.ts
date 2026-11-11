import type {
  CharacterSaved,
  CharacterSaveRequest,
  IllustrationRequest,
  JobAccepted,
  PreviewRequest,
  ReferenceRequest,
  RenderRequest,
  ScriptDraft,
  StoryboardRequest,
  StudioGateway,
} from "@/application/ports";
import type { Background } from "@/domain/background";
import type { Style } from "@/domain/captions";
import type { Config } from "@/domain/config";
import { readSaved, type ImageSettings, type ImageSettingsDraft } from "@/domain/illustration";
import type { VideoItem } from "@/domain/library";
import type { DownloadReport, StockClip } from "@/domain/stock";
import type { Voice } from "@/domain/voice";
import type { Writer, WriterDraft } from "@/domain/writer";

/**
 * Adaptador HTTP del puerto `StudioGateway`.
 *
 * Es el único archivo que sabe que detrás hay una API REST. Aquí se traducen
 * dos detalles del transporte que el dominio no tiene por qué conocer: los
 * sobres `{items: […]}` se desenvuelven a listas, y `default_style` pasa a
 * `defaultStyle`.
 *
 * Siempre rutas relativas: en desarrollo las reescribe next.config hacia el
 * backend del puerto 8000, y en el build exportado FastAPI sirve la interfaz
 * desde su mismo origen.
 */

type ConfigDto = { voices: Voice[]; default_style: Style; writer: string | null; generator: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
  });
  if (!response.ok) throw new Error(await detail(response));
  return response.json() as Promise<T>;
}

/** El backend explica el fallo en `detail`; si no llega, queda el código. */
async function detail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? `Error ${response.status}`;
  } catch {
    return `Error ${response.status}`;
  }
}

const post = <T,>(path: string, body: unknown): Promise<T> =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const httpGateway: StudioGateway = {
  async config(): Promise<Config> {
    const dto = await request<ConfigDto>("/api/config");
    return {
      voices: dto.voices,
      defaultStyle: dto.default_style,
      writer: dto.writer,
      generator: dto.generator,
    };
  },

  writer: () => request<Writer>("/api/writer"),

  saveWriter: (draft: WriterDraft) => post<Writer>("/api/writer", draft),

  requestScript: (topic, notes) => post<JobAccepted>("/api/script", { topic, notes }),

  /* Vale para cualquier trabajo encolado: guion o imagen. */
  jobStatus: (job) => request<Record<string, unknown>>(`/api/outcomes/${encodeURIComponent(job)}`),

  templateScript: (topic) => post<ScriptDraft>("/api/script/template", { topic, notes: "" }),

  async backgrounds(): Promise<Background[]> {
    const { items } = await request<{ items: Background[] }>("/api/backgrounds");
    return items;
  },

  async searchStock(query: string): Promise<StockClip[]> {
    const { items } = await request<{ items: StockClip[] }>(
      `/api/backgrounds/search?q=${encodeURIComponent(query)}`,
    );
    return items;
  },

  downloadStock: (query, ids) =>
    post<DownloadReport & { items: Background[] }>("/api/backgrounds/download", { query, ids }),

  async uploadBackground(file: File): Promise<Background[]> {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch("/api/backgrounds/upload", { method: "POST", body: form });
    // El cuerpo solo se puede leer una vez: se lee antes de mirar el estado.
    const body = (await response.json()) as { items?: Background[]; detail?: string };
    if (!response.ok) throw new Error(body.detail ?? `Error ${response.status}`);
    return body.items ?? [];
  },

  async deleteBackground(name: string): Promise<Background[]> {
    const { items } = await request<{ deleted: string; items: Background[] }>(
      `/api/backgrounds/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    );
    return items;
  },

  imageSettings: () => request<ImageSettings>("/api/images"),

  saveImageSettings: (draft: ImageSettingsDraft) => post<ImageSettings>("/api/images", draft),

  requestStoryboard: (payload: StoryboardRequest) => post<JobAccepted>("/api/storyboards", payload),

  requestIllustration: (payload: IllustrationRequest) =>
    post<JobAccepted>("/api/illustrations", payload),

  characters: async () => readSaved(await request<unknown>("/api/characters")),
  saveCharacter: (payload: CharacterSaveRequest) => post<CharacterSaved>("/api/characters", payload),
  repaintReference: (id: number, payload: ReferenceRequest) =>
    post<JobAccepted>(`/api/characters/${id}/reference`, payload),
  async deleteCharacter(id: number): Promise<void> {
    // 204 sin cuerpo: aquí no hay JSON que leer.
    const response = await fetch(`/api/characters/${id}`, { method: "DELETE" });
    if (!response.ok) throw new Error(await detail(response));
  },

  async previewFrame(payload: PreviewRequest): Promise<Blob> {
    const response = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await detail(response));
    return response.blob();
  },

  async startRender(payload: RenderRequest): Promise<number> {
    const { id } = await post<{ id: number; seconds: number }>("/api/render", payload);
    return id;
  },

  job: (id) => request<VideoItem>(`/api/jobs/${id}`),

  async videos(): Promise<VideoItem[]> {
    const { items } = await request<{ items: VideoItem[] }>("/api/videos");
    return items;
  },

  async deleteVideo(id: number): Promise<void> {
    await request<{ deleted: number }>(`/api/videos/${id}`, { method: "DELETE" });
  },

  thumbUrl: (thumb) => (thumb ? `/api/thumb/${thumb}` : ""),

  backgroundUrl: (name) => `/api/backgrounds/${encodeURIComponent(name)}/file`,
  referenceUrl: (name, version) =>
    `/api/references/${encodeURIComponent(name)}?v=${encodeURIComponent(version)}`,

  videoUrl: (id) => `/api/videos/${id}/file`,
};
