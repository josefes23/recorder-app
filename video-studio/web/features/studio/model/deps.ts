import type { StudioGateway } from "@/application/ports";

/**
 * Lo que cada slice necesita del entorno: con quién habla y cómo informa de
 * que está trabajando o de que algo ha fallado. Llega desde el proveedor, así
 * que ninguna feature importa la implementación HTTP.
 */
export type SliceDeps = {
  gateway: StudioGateway;
  /** Ejecuta la acción marcando ocupado y capturando el error. */
  run: <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;
  setError: (message: string | null) => void;
};
