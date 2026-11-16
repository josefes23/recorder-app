/**
 * Ajustes de producción de un video: formato, duración, diálogo y sonido.
 *
 * Hasta ahora todo era un reel vertical de 30–45 s con una sola voz. Las
 * mismas reglas viven en `app/domain/production.py`; los ajustes viajan al
 * servidor con cada encargo y se guardan dentro del estilo del video (clave
 * `production`), de donde «Reutilizar» los recupera.
 */
import type { Style } from "./captions.ts";
import type { DialogueVoices } from "./dialogue.ts";

export type FormatId = "9:16" | "16:9";
export type LengthId = "reel" | "corto";

export const FORMATS: { id: FormatId; label: string; hint: string }[] = [
  { id: "9:16", label: "Vertical 9:16", hint: "Reels, Shorts y TikTok" },
  { id: "16:9", label: "Horizontal 16:9", hint: "YouTube, como una película" },
];

export const LENGTHS: { id: LengthId; label: string; seconds: [number, number] }[] = [
  { id: "reel", label: "Reel · 30–45 s", seconds: [28, 48] },
  { id: "corto", label: "Cortometraje · 2–5 min", seconds: [110, 300] },
];

/** La horquilla de duración en la que el video no se queda corto ni pesa. */
export const lengthRange = (length: LengthId): [number, number] =>
  (LENGTHS.find((l) => l.id === length) ?? LENGTHS[0]).seconds;

/** Volumen de la música en los silencios, de 0 a 1: bajo, es fondo. */
export const DEFAULT_MUSIC_VOLUME = 0.25;

export type Production = {
  format: FormatId;
  length: LengthId;
  /** El guion se escribe como diálogo y cada personaje habla con su voz. */
  dialogue: boolean;
  voices: DialogueVoices;
  /** Pista de la galería de música, o "" para ninguna. */
  music: string;
  musicVolume: number;
  /** El sonido propio de los clips (los animados lo traen), debajo de la voz. */
  ambient: boolean;
};

export const DEFAULT_PRODUCTION: Production = {
  format: "9:16",
  length: "reel",
  dialogue: false,
  voices: {},
  music: "",
  musicVolume: DEFAULT_MUSIC_VOLUME,
  ambient: false,
};

/** Subtítulos que encajan en horizontal: más abajo, de menos líneas y más anchos. */
export const HORIZONTAL_CAPTIONS: Partial<Style> = { font_size: 64, y_ratio: 0.74, max_lines: 2, max_chars: 42 };

/** Lo que viaja al render. Las voces solo cuentan con el diálogo activado. */
export function forServer(production: Production) {
  return {
    format: production.format,
    length: production.length,
    voices: production.dialogue ? production.voices : {},
    music: production.music,
    music_volume: production.musicVolume,
    ambient: production.ambient,
  };
}

export const PRODUCTION_KEY = "production";

const isFormat = (value: unknown): value is FormatId => value === "9:16" || value === "16:9";
const isLength = (value: unknown): value is LengthId => value === "reel" || value === "corto";

/**
 * Separa lo que guardó el servidor dentro del estilo: el estilo de los
 * subtítulos por un lado y los ajustes de producción por otro. Un video de
 * antes no trae producción: sale un reel vertical con una voz.
 */
export function splitStoredStyle(style: unknown): { style: Partial<Style>; production: Production } {
  const { [PRODUCTION_KEY]: stored, ...captions } = (style ?? {}) as Record<string, unknown>;
  const raw = (stored ?? {}) as Record<string, unknown>;
  const voices =
    raw.voices && typeof raw.voices === "object"
      ? Object.fromEntries(
          Object.entries(raw.voices as Record<string, unknown>).filter(
            (entry): entry is [string, string] => typeof entry[1] === "string",
          ),
        )
      : {};
  return {
    style: captions as Partial<Style>,
    production: {
      format: isFormat(raw.format) ? raw.format : DEFAULT_PRODUCTION.format,
      length: isLength(raw.length) ? raw.length : DEFAULT_PRODUCTION.length,
      dialogue: Object.keys(voices).length > 0,
      voices,
      music: typeof raw.music === "string" ? raw.music : "",
      musicVolume: typeof raw.music_volume === "number" ? raw.music_volume : DEFAULT_MUSIC_VOLUME,
      ambient: raw.ambient === true,
    },
  };
}
