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
    { start: 0, text: "Primera frase.", description: "Uno.", motion: "" },
    { start: 6, text: "Segunda frase.", description: "Dos.", motion: "" },
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

test("al motor solo viajan fondo, segundo y la transición si eligió una", async () => {
  const { forEngine } = await import("./scene.ts");
  assert.deepEqual(forEngine([{ background: "a", start: 3, prompt: "p", job: "j", error: "e" }]), [
    { background: "a", start: 3 },
  ]);
  const transition = { kind: "fundido" as const, seconds: 0.8 };
  assert.deepEqual(forEngine([{ background: "a", start: 3, transition }]), [{ background: "a", start: 3, transition }]);
});

test("la transición de una escena se elige, sigue con su imagen nueva y se quita", async () => {
  const { withTransition, withJob, withImage } = await import("./scene.ts");
  const transition = { kind: "deslizar" as const, seconds: 0.6 };
  let scenes = withTransition([{ background: "a.jpg", start: 0 }, { background: "b.jpg", start: 4 }], 1, transition);
  assert.deepEqual(scenes[1].transition, transition);
  assert.equal(scenes[0].transition, undefined);

  scenes = withImage(withJob(scenes, 1, "im-1", "otra"), "im-1", "ia.jpg");
  assert.deepEqual(scenes[1].transition, transition);

  scenes = withTransition(scenes, 1, null);
  assert.equal("transition" in scenes[1], false);
});

test("el movimiento llega del guion visual y sigue con la escena al llegar su imagen", async () => {
  const { fromStoryboard, withJob, withImage, withClipJobAt, withClip } = await import("./scene.ts");
  let scenes = fromStoryboard([
    { start: 0, text: "Una.", description: "Ana sirve", motion: "el vapor sube" },
    { start: 5, text: "Dos.", description: "Ana sale", motion: "" },
  ]);
  assert.equal(scenes[0].motion, "el vapor sube");
  assert.equal("motion" in scenes[1], false);

  scenes = withImage(withJob(scenes, 0, "im-1", "Ana sirve"), "im-1", "ia.jpg");
  assert.deepEqual(scenes[0], { background: "ia.jpg", start: 0, prompt: "Ana sirve", motion: "el vapor sube" });
  scenes = withClip(withClipJobAt(scenes, 0, "an-1"), "an-1", "ia-mov.mp4");
  assert.equal(scenes[0].motion, "el vapor sube");
});

test("el movimiento se escribe tal cual y vacío se quita", async () => {
  const { withMotion } = await import("./scene.ts");
  const base: Scene[] = [scene("a.jpg", 0), scene("b.jpg", 5)];
  const typed = withMotion(base, 1, "la cámara ");
  assert.equal(typed[1].motion, "la cámara ");
  assert.equal(typed[0], base[0]);
  assert.deepEqual(withMotion(typed, 1, "")[1], { background: "b.jpg", start: 5 });
});

test("solo se pide movimiento donde hay o habrá una imagen que animar", async () => {
  const { takesMotion } = await import("./scene.ts");
  assert.equal(takesMotion(scene("ia.jpg", 0)), true);
  assert.equal(takesMotion({ background: null, start: 0, prompt: "taza", job: "im-1" }), true);
  assert.equal(takesMotion({ background: null, start: 0, prompt: "taza" }), true);
  assert.equal(takesMotion({ background: "ia-mov.mp4", start: 0, still: "ia.jpg" }), true);
  assert.equal(takesMotion(scene("pexels_1.mp4", 0)), false);
});

test("arrastrar un borde no desordena las escenas ni las deja sin duración", async () => {
  const { draggedStart, MIN_DRAG_SPAN } = await import("./scene.ts");
  const scenes = [{ background: "a", start: 0 }, { background: "b", start: 5 }, { background: "c", start: 10 }];
  assert.equal(draggedStart(scenes, 1, 7.34, 30), 7.3);
  assert.equal(draggedStart(scenes, 1, 0.1, 30), MIN_DRAG_SPAN);
  assert.equal(draggedStart(scenes, 1, 12, 30), 9.5);
  assert.equal(draggedStart(scenes, 2, 40, 30), 29.5);
  assert.equal(draggedStart(scenes, 0, 3, 30), 0); // la primera empieza siempre en 0
});

test("el estado de cada escena pone delante lo que pide atención", async () => {
  const { sceneState } = await import("./scene.ts");
  assert.equal(sceneState({ background: null, start: 0, job: "j" }), "painting");
  assert.equal(sceneState({ background: "a.jpg", start: 0, clipJob: "c" }), "animating");
  assert.equal(sceneState({ background: "a.jpg", start: 0, clipError: "x" }), "failed");
  assert.equal(sceneState({ background: null, start: 0 }), "empty");
  assert.equal(sceneState({ background: "a.jpg", start: 0 }), "ready");
});

test("varias escenas a la vez: misma transición, o fuera", async () => {
  const { withTransitionOn, withoutMany } = await import("./scene.ts");
  const scenes = [{ background: "a", start: 0 }, { background: "b", start: 5 }, { background: "c", start: 10 }];
  const fade = { kind: "fundido" as const, seconds: 0.7 };
  const faded = withTransitionOn(scenes, [1, 2], fade);
  assert.deepEqual(faded.map((s) => s.transition ?? null), [null, fade, fade]);
  assert.deepEqual(withTransitionOn(faded, [1, 2], null).map((s) => "transition" in s), [false, false, false]);
  assert.deepEqual(withoutMany(scenes, [0, 2]).map((s) => s.background), ["b"]);
});

test("intercambiar dos imágenes deja en su sitio los tiempos y las transiciones", async () => {
  const { swapImages } = await import("./scene.ts");
  const fade = { kind: "fundido" as const, seconds: 0.5 };
  const scenes = [
    { background: "a.jpg", start: 0, prompt: "A", motion: "sube" },
    { background: "b.jpg", start: 4, transition: fade },
    { background: null, start: 9, job: "im-1", prompt: "C" },
  ];
  const swapped = swapImages(scenes, 0, 2);
  assert.deepEqual(swapped[0], { background: null, start: 0, job: "im-1", prompt: "C" });
  assert.deepEqual(swapped[2], { background: "a.jpg", start: 9, prompt: "A", motion: "sube" });
  assert.equal(swapped[1], scenes[1]); // la de en medio, intacta
  assert.deepEqual(swapImages(swapImages(scenes, 1, 2), 1, 2), scenes); // dos veces, como estaba
  assert.equal(swapImages(scenes, 1, 1), scenes);
  assert.equal(swapImages(scenes, 1, 7), scenes);
});

test("mover una imagen corre las de en medio y se deshace al revés", async () => {
  const { moveImage } = await import("./scene.ts");
  const scenes = ["a", "b", "c", "d"].map((name, i) => ({ background: `${name}.jpg`, start: i * 3 }));
  const backgrounds = (list: { background: string | null }[]) => list.map((s) => s.background);
  const forward = moveImage(scenes, 0, 2);
  assert.deepEqual(backgrounds(forward), ["b.jpg", "c.jpg", "a.jpg", "d.jpg"]);
  assert.deepEqual(forward.map((s) => s.start), [0, 3, 6, 9]); // los tiempos no se mueven
  assert.deepEqual(backgrounds(moveImage(scenes, 3, 1)), ["a.jpg", "d.jpg", "b.jpg", "c.jpg"]);
  assert.deepEqual(moveImage(forward, 2, 0), scenes);
  // Con dos vecinas, mover es intercambiar.
  assert.deepEqual(backgrounds(moveImage(scenes, 1, 2)), ["a.jpg", "c.jpg", "b.jpg", "d.jpg"]);
});
