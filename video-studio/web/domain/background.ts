/** Si un fondo es una imagen fija, por su extensión: las mismas que `app/domain/background.py`. */
export const isImageFile = (name: string): boolean => /\.(jpe?g|png|webp|bmp)$/i.test(name);

/** Un clip o imagen de la galería, listo para usarse como fondo de escena. */
export type Background = {
  name: string;
  stem: string;
  group: string;
  kind: "video" | "image";
  duration: number;
  size_mb: number;
  thumb: string | null;
};
