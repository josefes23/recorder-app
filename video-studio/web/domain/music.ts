/** Una pista de la galería de música: las sube el usuario, de bibliotecas libres de derechos. */
export type Track = { name: string; duration: number; size_mb: number };

/** Los formatos que acepta la galería, los mismos que `app/domain/music.py`. */
export const MUSIC_ACCEPT = ".mp3,.m4a,.aac,.wav,.ogg,audio/*";
