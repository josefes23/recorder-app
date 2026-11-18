import assert from "node:assert/strict";
import { test } from "node:test";

import { clampSeconds, describeTransition, look, moment, planChanges, readTransition } from "./transition.ts";

test("una transición guardada se lee si vale y se ignora si no", () => {
  assert.deepEqual(readTransition({ kind: "fundido", seconds: 0.8 }), { kind: "fundido", seconds: 0.8 });
  assert.deepEqual(readTransition({ kind: "zoom" }), { kind: "zoom", seconds: 0.5 });
  assert.equal(readTransition({ kind: "estrella", seconds: 1 }), null);
  assert.equal(readTransition(null), null);
  assert.equal(readTransition("fundido"), null);
});

test("la duración queda dentro de lo que acepta el servidor, en décimas", () => {
  assert.equal(clampSeconds(0.05), 0.2);
  assert.equal(clampSeconds(3), 1.5);
  assert.equal(clampSeconds(0.30000000000000004), 0.3);
  assert.equal(clampSeconds(Number.NaN), 0.5);
});

test("el corte no dice cuánto dura; las demás, sí", () => {
  assert.equal(describeTransition({ kind: "corte", seconds: 0.5 }), "Corte");
  assert.equal(describeTransition({ kind: "fundido", seconds: 0.5 }), "Fundido encadenado · 0,5 s");
  assert.equal(describeTransition({ kind: "negro", seconds: 1 }), "Fundido a negro · 1,0 s");
});

test("los cambios se centran en el corte y no pasan de la escena más corta", () => {
  const changes = planChanges([0, 5, 5.6, 10], [{ kind: "fundido", seconds: 1 }, { kind: "corte", seconds: 0.5 }]);
  assert.equal(changes[0].at, 5);
  assert.ok(Math.abs(changes[0].seconds - 0.6) < 1e-9);
  assert.deepEqual(changes[1], { at: 5.6, kind: "corte", seconds: 0 });
  assert.deepEqual(moment(changes, 4.6), { index: 0, kind: "fundido", progress: null });
  assert.equal(moment(changes, 5).progress?.toFixed(2), "0.50");
  assert.equal(moment(changes, 5.6).index, 2);
});

test("la vista previa usa la misma cuenta que el render", () => {
  assert.equal(look("fundido", 0.25).alpha, 0.25);
  assert.equal(look("negro", 0.5).gainIn, 0);
  assert.equal(look("negro", 0.25).gainOut, 0.5);
  assert.equal(look("deslizar", 1).push, 1);
  const middle = look("zoom", 0.5);
  assert.equal(middle.alpha, 0.5);
  assert.ok(Math.abs(middle.zoomOut - 1.15) < 1e-9 && Math.abs(middle.zoomIn - 1.15) < 1e-9);
});
