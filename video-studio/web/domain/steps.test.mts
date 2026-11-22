import assert from "node:assert/strict";
import { test } from "node:test";

import { foldable, nextStep, STEP, stepStates, type StudioProgress } from "./steps.ts";

const base: StudioProgress = { verdict: "ok", music: false, scenes: [], timelineIssues: false, description: false, score: null };

test("un estudio recién abierto pide el guion y lo opcional no molesta", () => {
  const steps = stepStates({ ...base, verdict: "empty" });
  assert.deepEqual(steps.map((s) => s.state), ["todo", "done", "optional", "done", "optional", "optional", "optional"]);
  assert.equal(steps[0].note, "falta el guion");
});

test("las escenas avisan de lo que llega, de lo que falló y de los tiempos", () => {
  const ready = [{ background: "a.jpg", start: 0 }];
  assert.equal(stepStates({ ...base, scenes: ready })[6].state, "done");
  assert.equal(stepStates({ ...base, scenes: [...ready, { background: null, start: 5, job: "j" }] })[6].state, "busy");
  const failed = stepStates({ ...base, scenes: [...ready, { background: "b.jpg", start: 5, clipError: "x" }] })[6];
  assert.deepEqual([failed.state, failed.note], ["warn", "1 escena por revisar"]);
  assert.equal(stepStates({ ...base, scenes: ready, timelineIssues: true })[6].state, "warn");
});

test("solo se pliegan los pasos listos", () => {
  const steps = stepStates({ ...base, verdict: "short", music: true, description: true });
  assert.equal(steps[0].state, "warn");
  assert.deepEqual(foldable(steps), [2, 3, 4, 5]);
});

test("Optimizar va antes de Escenas: las imágenes se pintan cuando el guion ya está decidido", () => {
  const steps = stepStates(base);
  assert.equal(steps[STEP.scenes - 1].title, "Escenas");
  assert.equal(steps[STEP.growth - 1].title, "Optimizar");
  assert.ok(STEP.growth < STEP.scenes);
});

test("Escenas es el último paso: ya no hay acabado", () => {
  const steps = stepStates(base);
  assert.equal(steps.length, STEP.scenes);
  assert.equal(steps.at(-1)?.title, "Escenas");
});

test("qué sigue: primero el guion, luego Optimizar, luego lo que falte, al final renderizar", () => {
  assert.deepEqual(
    [nextStep(stepStates({ ...base, verdict: "empty" })).n, nextStep(stepStates({ ...base, verdict: "empty" })).kind],
    [STEP.script, "fix"],
  );
  const suggest = nextStep(stepStates(base));
  assert.deepEqual([suggest.n, suggest.kind], [STEP.growth, "suggest"]);

  const scored = { ...base, score: 80 };
  assert.deepEqual([nextStep(stepStates(scored)).n, nextStep(stepStates(scored)).kind], [0, "render"]);
  const broken = [{ background: "a.jpg", start: 0 }, { background: "b.jpg", start: 5, clipError: "x" }];
  const warn = nextStep(stepStates({ ...scored, scenes: broken }));
  assert.deepEqual([warn.n, warn.kind], [STEP.scenes, "fix"]);
  const waiting = nextStep(stepStates({ ...scored, scenes: [{ background: null, start: 0, job: "j" }] }));
  assert.deepEqual([waiting.n, waiting.kind], [STEP.scenes, "wait"]);
});
