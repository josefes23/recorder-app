/** Un clip del catálogo de Pexels, tal como se ve antes de descargarlo. */
export type StockClip = {
  id: number;
  /** Fotograma de muestra: con él se elige sin bajar el archivo. */
  preview: string;
  duration: number;
  width: number;
  height: number;
  size_mb: number;
  author: string;
  /** Página del clip en Pexels. */
  url: string;
  /** La versión más ligera del clip, para verlo en movimiento antes de decidir. */
  play: string;
  /** Nombre que tendrá en la galería. */
  name: string;
  /** Ya está en la galería: no hace falta volver a bajarlo. */
  owned: boolean;
};

/** Una búsqueda y lo que devolvió. La búsqueda da nombre a los archivos al descargar. */
export type StockSearch = { query: string; clips: StockClip[] };

/** Cómo acabó una descarga: qué entró, qué ya estaba y qué falló. */
export type DownloadReport = { added: string[]; existing: string[]; failed: string[] };

/** Una línea para la interfaz: «2 clips nuevos · 1 ya estaba · falló x: motivo». */
export function describeDownload(report: DownloadReport): string {
  const parts: string[] = [];
  const added = report.added.length;
  const existing = report.existing.length;
  if (added) parts.push(added === 1 ? "1 clip nuevo" : `${added} clips nuevos`);
  if (existing) parts.push(existing === 1 ? "1 ya estaba" : `${existing} ya estaban`);
  parts.push(...report.failed.map((reason) => `falló ${reason}`));
  return parts.join(" · ");
}

/** Tras descargar, los clips que entraron (o ya estaban) pasan a ser de la galería. */
export function markOwned(clips: StockClip[], report: DownloadReport): StockClip[] {
  const names = new Set([...report.added, ...report.existing]);
  return clips.map((clip) => (names.has(clip.name) ? { ...clip, owned: true } : clip));
}

/** Tras borrar un fondo de la galería, su clip vuelve a poder marcarse. */
export function releaseOwned(clips: StockClip[], name: string): StockClip[] {
  return clips.map((clip) => (clip.name === name ? { ...clip, owned: false } : clip));
}
