import assert from "node:assert/strict";
import { test } from "node:test";

import { foldable, stepStates, type StudioProgress } from "./steps.ts";

const base: StudioProgress = { verdict: "ok", music: false, scenes: [], timelineIssues: false, description: false };

test("un estudio recién abierto pide el guion y lo opcional no molesta", () => {
  const steps = stepStates({ ...base, verdict: "empty" });
  assert.deepEqual(steps.map((s) => s.state), ["todo", "done", "optional", "done", "optional", "optional"]);
  assert.equal(steps[0].note, "falta el guion");
});

test("las escenas avisan de lo que llega, de lo que falló y de los tiempos", () => {
  const ready = [{ background: "a.jpg", start: 0 }];
  assert.equal(stepStates({ ...base, scenes: ready })[4].state, "done");
  assert.equal(stepStates({ ...base, scenes: [...ready, { background: null, start: 5, job: "j" }] })[4].state, "busy");
  const failed = stepStates({ ...base, scenes: [...ready, { background: "b.jpg", start: 5, clipError: "x" }] })[4];
  assert.deepEqual([failed.state, failed.note], ["warn", "1 escena por revisar"]);
  assert.equal(stepStates({ ...base, scenes: ready, timelineIssues: true })[4].state, "warn");
});

test("solo se pliegan los pasos listos", () => {
  const steps = stepStates({ ...base, verdict: "short", music: true, description: true });
  assert.equal(steps[0].state, "warn");
  assert.deepEqual(foldable(steps), [2, 3, 4, 6]);
});
