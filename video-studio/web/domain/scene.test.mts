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

test("al borrar un fondo de la galería se van las escenas que lo usaban", async () => {
  const { withoutBackground } = await import("./scene.ts");
  const left = withoutBackground([scene("a", 0), scene("b", 5), scene("a", 9)], "a");
  assert.deepEqual(left, [scene("b", 5)]);
});

test("las escenas del guion visual esperan cada una su imagen, y llegan en cualquier orden", async () => {
  const { fromStoryboard, withJob, withImage, withFailure, pendingImages } = await import("./scene.ts");
  let scenes = fromStoryboard([
    { start: 0, text: "Primera frase.", description: "Uno." },
    { start: 6, text: "Segunda frase.", description: "Dos." },
  ]);
  assert.deepEqual(scenes[1], { background: null, start: 6, prompt: "Dos." });
  assert.equal(pendingImages(scenes), 0);

  scenes = withJob(withJob(scenes, 0, "im-1", "Uno."), 1, "im-2", "Dos.");
  assert.equal(pendingImages(scenes), 2);

  scenes = withImage(scenes, "im-2", "ia-x_2.jpg");
  assert.deepEqual(scenes[1], { background: "ia-x_2.jpg", start: 6, prompt: "Dos." });
  scenes = withFailure(scenes, "im-1", "sin cupo");
  assert.deepEqual(scenes[0], {
    background: null,
    start: 0,
    prompt: "Uno.",
    job: undefined,
    error: "sin cupo",
    review: undefined,
  });
  assert.equal(pendingImages(scenes), 0);

  // Una imagen que ya no espera nadie no toca nada.
  assert.deepEqual(withImage(scenes, "im-9", "otra.jpg"), scenes);
});

test("pedir otra imagen la marca en su escena, o añade una al final", async () => {
  const { withJob } = await import("./scene.ts");
  const base = [{ ...scene("a", 0), error: "falló" }];
  assert.deepEqual(withJob(base, 0, "im-1", "taza"), [
    { background: "a", start: 0, error: undefined, review: undefined, job: "im-1", prompt: "taza" },
  ]);
  assert.deepEqual(withJob(base, null, "im-2", "mar")[1], {
    background: null,
    start: 8,
    job: "im-2",
    prompt: "mar",
    error: undefined,
    review: undefined,
  });
});

test("la imagen llega con su revisión, y la pierde al cambiarla", async () => {
  const { withBackground, withImage, withJob } = await import("./scene.ts");
  const review = { status: "approved" as const, reviewer: "Claude", attempts: 1, problems: [], fixed: [], detail: "" };
  const waiting: Scene[] = [{ background: null, start: 0, prompt: "taza", job: "im-1" }];
  const done = withImage(waiting, "im-1", "ia.jpg", review);
  assert.deepEqual(done[0], { background: "ia.jpg", start: 0, prompt: "taza", review });
  assert.equal(withImage(waiting, "im-1", "ia.jpg")[0].review, undefined);
  assert.equal(withJob(done, 0, "im-2", "taza")[0].review, undefined);
  assert.equal(withBackground(done, 0, "pexels_1.mp4")[0].review, undefined);
});

test("elegir un fondo a mano deja de esperar la imagen pedida", async () => {
  const { withBackground, withImage } = await import("./scene.ts");
  const waiting: Scene[] = [{ background: null, start: 0, prompt: "taza", job: "im-1" }];
  const chosen = withBackground(waiting, 0, "pexels_1.mp4");
  assert.equal(chosen[0].job, undefined);
  assert.equal(withImage(chosen, "im-1", "ia.jpg")[0].background, "pexels_1.mp4");
});

test("al motor solo viajan fondo y segundo", async () => {
  const { forEngine } = await import("./scene.ts");
  assert.deepEqual(forEngine([{ background: "a", start: 3, prompt: "p", job: "j", error: "e" }]), [
    { background: "a", start: 3 },
  ]);
});
