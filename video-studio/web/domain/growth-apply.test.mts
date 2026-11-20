import assert from "node:assert/strict";
import { test } from "node:test";

import { planApplication, readApplication, scriptTimingNote, type Application, type ExistingWork } from "./growth.ts";

const NOTHING_DONE: ExistingWork = { aiScenes: 0, canPaint: true, voiceTake: false };
const ALL_DONE: ExistingWork = { aiScenes: 6, canPaint: true, voiceTake: true };
const NEW_SCRIPT: Application = { summary: "Gancho nuevo", script: "Otro guion.", title: null, description: null };

test("un guion nuevo con escenas pintadas y voz hechas obliga a preguntar qué rehacer", () => {
  const plan = planApplication(NEW_SCRIPT, ALL_DONE);
  assert.deepEqual(plan.changes, ["el guion"]);
  assert.deepEqual(plan.regenerates, ["scenes", "voice"]);
});

test("un guion nuevo sin nada hecho todavía se aplica sin preguntar", () => {
  assert.deepEqual(planApplication(NEW_SCRIPT, NOTHING_DONE).regenerates, []);
});

test("título y descripción se cambian sin preguntar aunque haya todo hecho", () => {
  const plan = planApplication({ summary: "", script: null, title: "Otro *título*", description: "Otra" }, ALL_DONE);
  assert.deepEqual(plan.changes, ["el título", "la descripción"]);
  assert.deepEqual(plan.regenerates, []);
});

test("las escenas de stock o sin generador de imágenes no se rehacen", () => {
  assert.deepEqual(planApplication(NEW_SCRIPT, { aiScenes: 0, canPaint: true, voiceTake: false }).regenerates, []);
  assert.deepEqual(planApplication(NEW_SCRIPT, { aiScenes: 5, canPaint: false, voiceTake: false }).regenerates, []);
});

test("una recomendación que no cambia nada no tiene cambios ni nada que rehacer", () => {
  const plan = planApplication({ summary: "Se arregla publicando de noche", script: null, title: null, description: null }, ALL_DONE);
  assert.deepEqual(plan.changes, []);
  assert.deepEqual(plan.regenerates, []);
});

test("lo que llega del servidor se lee y un campo vacío cuenta como no cambiado", () => {
  const read = readApplication({ result: { summary: "x", script: "  ", title: null, description: "Nueva" } });
  assert.deepEqual(read, { summary: "x", script: null, title: null, description: "Nueva" });
  assert.throws(() => readApplication({}), /vacía/);
});

test("Optimizar avisa cuándo sale caro cambiar el guion", () => {
  assert.equal(scriptTimingNote(NOTHING_DONE).late, false);
  assert.match(scriptTimingNote(ALL_DONE).text, /la toma de voz y las imágenes de las escenas/);
  assert.match(scriptTimingNote({ aiScenes: 0, canPaint: true, voiceTake: true }).text, /Ya hay la toma de voz:/);
  assert.equal(scriptTimingNote({ aiScenes: 4, canPaint: false, voiceTake: false }).late, false);
});
