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
