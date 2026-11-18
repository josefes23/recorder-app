import assert from "node:assert/strict";
import { test } from "node:test";

import { inFlight, whatWouldBeLost } from "./fresh-start.ts";

const blank = { topic: "", script: "", description: "", scenes: [], rendering: false };

test("un estudio en blanco no tiene nada que perder", () => {
  assert.deepEqual(whatWouldBeLost({ ...blank, topic: "  ", script: " " }), []);
  assert.deepEqual(inFlight(blank), []);
});

test("se nombra lo que se perdería", () => {
  const work = {
    ...blank,
    script: "Hola.",
    description: "Texto",
    scenes: [{ background: "a.jpg", start: 0 }, { background: "b.jpg", start: 4 }],
  };
  assert.deepEqual(whatWouldBeLost(work), ["el tema y el guion", "las 2 escenas", "la descripción"]);
  assert.deepEqual(whatWouldBeLost({ ...blank, scenes: [{ background: "a.jpg", start: 0 }] }), ["la escena"]);
});

test("se avisa de lo que viene en camino", () => {
  assert.equal(inFlight({ ...blank, scenes: [{ background: null, start: 0, job: "j" }] }).length, 1);
  assert.equal(inFlight({ ...blank, rendering: true }).length, 1);
});
