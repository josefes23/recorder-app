import type { Style } from "./captions";
import type { Voice } from "./voice";

/** Estado de la cuenta de ElevenLabs: con clave, sus voces se suman a las de edge-tts. */
export type ElevenLabs = {
  ready: boolean;
  model: string;
  voices: number;
  /** Por qué no se pudieron traer las voces (clave rechazada, sin red…), o null. */
  problem: string | null;
};

/** Lo que el servidor dicta al arrancar y la interfaz no puede inventar. */
export type Config = {
  voices: Voice[];
  elevenlabs: ElevenLabs;
  defaultStyle: Style;
  /** Modelo que redacta el guion, o null si no hay clave de API. */
  writer: string | null;
  /** Ruta del motor que hay detrás, para poder situarlo si algo falla. */
  generator: string;
};
