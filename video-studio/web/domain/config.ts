import type { Style } from "./captions";
import type { Voice } from "./voice";

/** Lo que el servidor dicta al arrancar y la interfaz no puede inventar. */
export type Config = {
  voices: Voice[];
  defaultStyle: Style;
  /** Modelo que redacta el guion, o null si no hay clave de API. */
  writer: string | null;
  /** Ruta del motor que hay detrás, para poder situarlo si algo falla. */
  generator: string;
};
