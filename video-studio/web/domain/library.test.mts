import assert from "node:assert/strict";
import { test } from "node:test";

import { clockTime, countByStatus, dayLabel, filterVideos, DEFAULT_FILTER, type VideoItem } from "./library.ts";

const video = (id: number, over: Partial<VideoItem> = {}): VideoItem => ({
  id, topic: `Tema ${id}`, script: "", voice: "v", style: {}, scenes: [], filename: "x.mp4",
  duration: 40, size_mb: 5, captions: 10, status: "done", error: null, created_at: "2026-11-12 16:38:24", ...over,
});

const items = [
  video(1, { topic: "¿Por qué ayunó Jesús?", description: "#fe #biblia" }),
  video(2, { topic: "Café de la mañana", status: "error", error: "ffmpeg", filename: null }),
  video(3, { topic: "Montañas", style: { production: { format: "16:9" } } as never, script: "Un viaje largo" }),
  video(4, { topic: "En cola", status: "queued", filename: null }),
];

test("buscar no distingue tildes ni mayúsculas y pide todas las palabras", () => {
  const ids = (query: string) => filterVideos(items, { ...DEFAULT_FILTER, query }).map((v) => v.id);
  assert.deepEqual(ids("AYUNO jesus"), [1]);
  assert.deepEqual(ids("biblia"), [1]); // también en la descripción
  assert.deepEqual(ids("viaje"), [3]); // y en el guion
  assert.deepEqual(ids("ayuno café"), []);
  assert.deepEqual(ids("  "), [1, 2, 3, 4]);
});

test("se filtra por estado y por formato, y se cuenta cada estado", () => {
  assert.deepEqual(filterVideos(items, { ...DEFAULT_FILTER, status: "failed" }).map((v) => v.id), [2]);
  assert.deepEqual(filterVideos(items, { ...DEFAULT_FILTER, status: "active" }).map((v) => v.id), [4]);
  assert.deepEqual(filterVideos(items, { ...DEFAULT_FILTER, format: "16:9" }).map((v) => v.id), [3]);
  assert.deepEqual(filterVideos(items, { ...DEFAULT_FILTER, format: "9:16" }).map((v) => v.id), [1, 2, 4]);
  assert.deepEqual(countByStatus(items), { all: 4, done: 2, failed: 1, active: 1 });
});

test("la duración y la fecha se leen de un vistazo", () => {
  assert.equal(clockTime(43.4), "0:43");
  assert.equal(clockTime(125), "2:05");
  assert.equal(clockTime(null), "");
  const now = new Date(2026, 10, 17, 10, 0);
  assert.equal(dayLabel("2026-11-17 09:05:00", now), "hoy 9:05");
  assert.equal(dayLabel("2026-11-16T21:42:18", now), "ayer 21:42");
  assert.equal(dayLabel("2026-11-12 16:38:24", now), "12 nov");
  assert.equal(dayLabel("2025-03-03 10:00:00", now), "3 mar 2025");
});
