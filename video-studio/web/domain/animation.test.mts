import assert from "node:assert/strict";
import { test } from "node:test";

import { clipSeconds, estimateCost, exceedsClip, formatUsd } from "./animation.ts";
import { coverCandidates, firstBackground } from "./cover.ts";
import {
  animatable,
  pendingClips,
  withBackground,
  withClip,
  withClipFailure,
  withClipFailureOn,
  withClipJobAt,
  withClipJobOn,
  withImage,
  withJob,
  withStillImage,
  withoutBackground,
  type Scene,
} from "./scene.ts";

const scene = (background: string | null, start = 0, extra: Partial<Scene> = {}): Scene => ({
  background,
  start,
  ...extra,
});

test("el clip cubre el tramo redondeando hacia arriba, entre 3 y 15 s", () => {
  assert.equal(clipSeconds(6), 6);
  assert.equal(clipSeconds(6.0000001), 6);
  assert.equal(clipSeconds(6.2), 7);
  assert.equal(clipSeconds(1), 3);
  assert.equal(clipSeconds(40), 15);
  assert.equal(exceedsClip(15), false);
  assert.equal(exceedsClip(16), true);
});

test("el costo suma los segundos que se pedirán de verdad", () => {
  // 6 + 7 + 3 = 16 s a 0,07 US$/s
  assert.equal(estimateCost([6, 6.2, 1], 0.07).toFixed(2), "1.12");
  assert.equal(formatUsd(1.12), "US$ 1,12");
});

test("se anima la imagen de la escena, o su original si ya lleva un clip", () => {
  assert.equal(animatable(scene("ia-a.jpg")), "ia-a.jpg");
  assert.equal(animatable(scene("ia-a-mov-1.mp4", 0, { still: "ia-a.jpg" })), "ia-a.jpg");
  assert.equal(animatable(scene("bosque.mp4")), null); // un clip de Pexels ya se mueve
  assert.equal(animatable(scene(null)), null);
  assert.equal(animatable(scene("ia-a.jpg", 0, { clipJob: "an-1" })), null); // ya se está animando
  assert.equal(animatable(scene("ia-a.jpg", 0, { job: "im-1" })), null); // espera otra imagen
});

test("el clip llega a la escena que lo esperaba y guarda su imagen", () => {
  const scenes = withClipJobAt([scene("ia-a.jpg"), scene("ia-b.jpg", 6)], 1, "an-1");
  assert.equal(pendingClips(scenes), 1);

  const done = withClip(scenes, "an-1", "ia-b-mov-1.mp4");
  assert.deepEqual(done[1], { background: "ia-b-mov-1.mp4", start: 6, still: "ia-b.jpg" });
  assert.equal(done[0], scenes[0]);

  // Animar otra vez parte de la imagen original, no del clip anterior
  const again = withClip(withClipJobAt(done, 1, "an-2"), "an-2", "ia-b-mov-2.mp4");
  assert.equal(again[1].still, "ia-b.jpg");
  assert.equal(again[1].background, "ia-b-mov-2.mp4");
});

test("la imagen que acaba de llegar se marca por su nombre, no por su posición", () => {
  const scenes = withClipJobOn([scene("ia-a.jpg"), scene("ia-b.jpg", 6)], "ia-b.jpg", "an-1");
  assert.equal(scenes[1].clipJob, "an-1");
  assert.equal(scenes[0].clipJob, undefined);
  assert.equal(withClipFailureOn(scenes, "ia-a.jpg", "sin clave")[0].clipError, "sin clave");
});

test("un clip que llega para una imagen ya cambiada no pisa nada", () => {
  const waiting = withClipJobAt([scene("ia-a.jpg")], 0, "an-1");
  const changed = withBackground(waiting, 0, "bosque.mp4");
  assert.equal(changed[0].clipJob, undefined);
  assert.deepEqual(withClip(changed, "an-1", "ia-a-mov-1.mp4"), changed);

  // Pedir otra imagen también olvida la animación anterior
  const animated = withClip(waiting, "an-1", "ia-a-mov-1.mp4");
  const repainting = withJob(animated, 0, "im-2", "otra cosa");
  assert.equal(repainting[0].still, undefined);
  const repainted = withImage(repainting, "im-2", "ia-c.jpg");
  assert.equal(repainted[0].background, "ia-c.jpg");
  assert.equal(repainted[0].still, undefined);
});

test("un fallo queda en su escena y se puede volver a la imagen fija", () => {
  const failed = withClipFailure(withClipJobAt([scene("ia-a.jpg")], 0, "an-1"), "an-1", "Sin cupo");
  assert.equal(failed[0].clipError, "Sin cupo");
  assert.equal(failed[0].clipJob, undefined);

  const animated = withClip(withClipJobAt([scene("ia-a.jpg")], 0, "an-2"), "an-2", "ia-a-mov-2.mp4");
  const back = withStillImage(animated, 0);
  assert.equal(back[0].background, "ia-a.jpg");
  assert.equal(back[0].still, undefined);
});

test("borrar la imagen de un clip deja la escena con el clip y sin vuelta atrás", () => {
  const scenes = [scene("ia-a-mov-1.mp4", 0, { still: "ia-a.jpg" }), scene("ia-a.jpg", 6)];
  assert.deepEqual(withoutBackground(scenes, "ia-a.jpg"), [scene("ia-a-mov-1.mp4", 0)]);
});

test("la portada prefiere la imagen fija de una escena animada", () => {
  const scenes = [scene("ia-a-mov-1.mp4", 0, { still: "ia-a.jpg" }), scene("bosque.mp4", 6)];
  assert.deepEqual(coverCandidates(scenes), ["ia-a.jpg", "ia-a-mov-1.mp4", "bosque.mp4"]);
  assert.equal(firstBackground(scenes), "ia-a.jpg");
});
