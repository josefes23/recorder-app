import type { AnimationSettings } from "@/domain/animation";
import type { Background } from "@/domain/background";
import type { Track } from "@/domain/music";
import type { FormatId, LengthId, forServer } from "@/domain/production";
import type { Style } from "@/domain/captions";
import type { Config } from "@/domain/config";
import type { Cover } from "@/domain/cover";
import type {
  Character,
  ImageSettings,
  ImageSettingsDraft,
  Kind,
  SavedCharacter,
} from "@/domain/illustration";
import type { VideoItem } from "@/domain/library";
import type { Scene } from "@/domain/scene";
import type { DownloadReport, StockClip } from "@/domain/stock";
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

export type WaitOptions = {
  /**
   * Cuánto esperar antes de darlo por perdido. Por defecto, cinco minutos; un
   * clip animado tarda minutos y puede esperar turno, así que pide más.
   */
  giveUpMs?: number;
};

/** Espera el desenlace de un trabajo encolado. */
export interface JobTracker {
  waitFor(job: string, options?: WaitOptions): Promise<Record<string, unknown>>;
}

export type PreviewRequest = {
  caption: string;
  topic: string;
  background: string | null;
  style: Style;
  format: FormatId;
};

export type StoryboardRequest = {
  topic: string;
  script: string;
  /** El estilo que pide el usuario; el modelo lo concreta. */
  style: string;
  /** El reparto que ya está en el video: el guion visual lo incluye entero. */
  characters: Character[];
  /** Reel (hasta 8 escenas) o cortometraje (hasta 30). */
  length: LengthId;
  /** Dónde caben las caras: vertical u horizontal. */
  format: FormatId;
};

export type CharacterSaveRequest = {
  name: string;
  traits: string;
  kind: Kind;
  /** El estilo del video desde el que se guarda: con él se pinta su imagen de referencia. */
  look: string;
  provider: string;
  model: string;
};

/** Guardado al momento; `job` es su imagen de referencia, o null si la que tenía sigue valiendo. */
export type CharacterSaved = { character: SavedCharacter; job: string | null };

export type ReferenceRequest = { look: string; provider: string; model: string };

export type IllustrationRequest = {
  topic: string;
  /** Qué debe mostrar la imagen. */
  description: string;
  /** La guía visual del video, común a todas sus escenas. */
  look: string;
  characters: Character[];
  seed: number | null;
  provider: string;
  model: string;
  /** Que el modelo del guion la revise y la repinte si ve fallos. */
  review: boolean;
  /** Para corregir una imagen en vez de pintar otra: su nombre en la galería… */
  source?: string;
  /** …y qué está mal en ella. Al corregir, la descripción puede ir vacía. */
  correction?: string;
  /** La imagen sale con la orientación del video. */
  format: FormatId;
};

export type AnimationRequest = {
  topic: string;
  /** La imagen de la galería que se anima: será el primer fotograma. */
  source: string;
  /** Segundos enteros del clip (3 a 15): lo que dura el tramo de la escena. */
  seconds: number;
  /** Qué pasa en la escena: ayuda al modelo a saber qué mover. */
  description: string;
  look: string;
  characters: Character[];
  seed: number | null;
  /** El clip sale con la orientación del video. */
  format: FormatId;
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
  /** Se guarda con el video para descargarla después; null deja la de por defecto. */
  cover: Cover | null;
  /** El texto con que se publica; se guarda con el video para copiarlo después. */
  description: string;  /** Formato, duración, voces del diálogo, música y sonido ambiente (`forServer`). */
  production: ReturnType<typeof forServer>;
};

export type DescriptionRequest = { topic: string; script: string; title: string };

/** La portada tal como está en el estudio; el tema da color al degradado si no hay imagen. */
export type CoverRequest = Cover & { topic: string; format: FormatId };

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
  /** Encola la redacción: un reel o un cortometraje, narrado o en diálogo. */
  requestScript(topic: string, notes: string, length: LengthId, dialogue: boolean): Promise<JobAccepted>;
  /** Desenlace de un trabajo: la red de seguridad si su evento no llegó. */
  jobStatus(job: string): Promise<Record<string, unknown>>;
  /** La plantilla es local: se resuelve en la misma petición. */
  templateScript(topic: string): Promise<ScriptDraft>;

  backgrounds(): Promise<Background[]>;
  /** Clips de Pexels que encajan con la búsqueda, con miniatura y sin bajar nada. */
  searchStock(query: string, format: FormatId): Promise<StockClip[]>;
  /** Baja a la galería los clips marcados de esa búsqueda; devuelve la galería al día. */
  downloadStock(query: string, ids: number[], format: FormatId): Promise<DownloadReport & { items: Background[] }>;

  /** La galería de música: pistas que subió el usuario. */
  music(): Promise<Track[]>;
  uploadMusic(file: File): Promise<Track[]>;
  deleteMusic(name: string): Promise<Track[]>;
  /** La pista entera, para escucharla. */
  musicUrl(name: string): string;
  uploadBackground(file: File): Promise<Background[]>;
  /** Borra un fondo de la galería, archivo incluido; devuelve la galería al día. */
  deleteBackground(name: string): Promise<Background[]>;

  imageSettings(): Promise<ImageSettings>;
  saveImageSettings(draft: ImageSettingsDraft): Promise<ImageSettings>;
  /**
   * Encola el guion visual: estilo, reparto y qué se ve en cada escena. Lo
   * escribe el modelo del guion y llega por el flujo de eventos.
   */
  requestStoryboard(request: StoryboardRequest): Promise<JobAccepted>;
  /** Encola una imagen; llega por el flujo de eventos y entra en la galería. */
  requestIllustration(request: IllustrationRequest): Promise<JobAccepted>;

  /** Con qué se animan las escenas, su precio orientativo y si la clave está puesta. */
  animationSettings(): Promise<AnimationSettings>;
  /** Encola la animación de una imagen; el clip llega por el flujo de eventos y entra en la galería. */
  requestAnimation(request: AnimationRequest): Promise<JobAccepted>;

  /** La biblioteca de elementos que se repiten entre videos, lo último primero. */
  characters(): Promise<SavedCharacter[]>;
  /** Guarda (o pone al día por nombre) y encarga su imagen de referencia si hace falta. */
  saveCharacter(request: CharacterSaveRequest): Promise<CharacterSaved>;
  repaintReference(id: number, request: ReferenceRequest): Promise<JobAccepted>;
  deleteCharacter(id: number): Promise<void>;

  previewFrame(request: PreviewRequest): Promise<Blob>;

  /** La portada a tamaño completo (1080x1920, JPEG): la misma sirve para verla y para bajarla. */
  coverImage(request: CoverRequest): Promise<Blob>;
  /** Encola la propuesta de títulos gancho; llegan por el flujo de eventos. */
  requestTitles(topic: string, script: string): Promise<JobAccepted>;
  /** Encola la descripción para publicar; llega por el flujo de eventos. */
  requestDescription(request: DescriptionRequest): Promise<JobAccepted>;

  startRender(request: RenderRequest): Promise<number>;
  job(id: number): Promise<VideoItem>;

  videos(): Promise<VideoItem[]>;
  deleteVideo(id: number): Promise<void>;

  /** URLs que sirve el propio backend; la interfaz no arma rutas a mano. */
  thumbUrl(thumb: string | null): string;
  /** El archivo entero de un fondo, para verlo o reproducirlo a tamaño grande. */
  backgroundUrl(name: string): string;
  /** La imagen de referencia de un elemento guardado; `version` evita la copia vieja del navegador al repintarla. */
  referenceUrl(name: string, version: string): string;
  videoUrl(id: number): string;
  /** La portada guardada con ese video, como descarga. */
  coverUrl(id: number): string;
}
