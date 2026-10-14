import assert from "node:assert/strict";
import { test } from "node:test";

import { appended, buildTimeline, type Scene } from "./scene.ts";

const scene = (background: string, start: number): Scene => ({ background, start });

test("reparte la duración de la voz entre las escenas", () => {
  const timeline = buildTimeline([scene("a", 0), scene("b", 10)], 30);

  assert.equal(timeline.total, 30);
  assert.deepEqual(
    timeline.segments.map((s) => s.span),
    [10, 20],
  );
  assert.deepEqual(timeline.late, []);
  assert.equal(timeline.disordered, false);
});

test("la primera escena arranca en 0 aunque diga otra cosa", () => {
  const timeline = buildTimeline([scene("a", 7), scene("b", 10)], 30);
  assert.equal(timeline.segments[0].start, 0);
});

test("señala las escenas que entran después de que acabe la voz", () => {
  const timeline = buildTimeline([scene("a", 0), scene("b", 20), scene("c", 40)], 30);

  assert.deepEqual(timeline.late, [3]);
  // La barra se estira hasta la última escena para que se vea el tramo muerto
  assert.equal(timeline.total, 40);
});

test("cada tramo sabe dónde empieza y dónde acaba", () => {
  const timeline = buildTimeline([scene("a", 0), scene("b", 10)], 30);

  assert.deepEqual(
    timeline.segments.map((s) => [s.start, s.end]),
    [[0, 10], [10, 30]],
  );
});

test("avisa de cuántas veces se repetirá un clip corto", () => {
  // Tramos de 10 y 20 s con clips de 4 y 30 s
  const timeline = buildTimeline([scene("a", 0), scene("b", 10)], 30, [4, 30]);

  // Misma cuenta que el motor: floor(10 / 4) + 1 = 3 copias encadenadas
  assert.equal(timeline.segments[0].repeats, 3);
  // El clip cubre el tramo de sobra, así que no se repite
  assert.equal(timeline.segments[1].repeats, 1);
});

test("sin duración conocida no se promete repetición", () => {
  // Las imágenes llegan con cero: el motor las estira con un zoom, no las repite
  const timeline = buildTimeline([scene("a", 0)], 30, [0]);
  assert.equal(timeline.segments[0].repeats, 1);

  const sinDatos = buildTimeline([scene("a", 0)], 30);
  assert.equal(sinDatos.segments[0].repeats, 1);
});

test("detecta segundos desordenados", () => {
  const timeline = buildTimeline([scene("a", 0), scene("b", 20), scene("c", 5)], 30);
  assert.equal(timeline.disordered, true);
});

test("encadena la escena nueva al final", () => {
  assert.deepEqual(appended([], "a"), [{ background: "a", start: 0 }]);
  assert.deepEqual(appended([scene("a", 0)], "b"), [
    { background: "a", start: 0 },
    { background: "b", start: 8 },
  ]);
});
