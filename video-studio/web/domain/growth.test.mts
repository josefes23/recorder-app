import assert from "node:assert/strict";
import { test } from "node:test";

import { growthBlocker, readGrowth, scoreTone, withHook } from "./growth.ts";

test("cada consejo dice qué le falta para pedirse", () => {
  assert.match(growthBlocker("retention", "tema", " ") ?? "", /guion/);
  assert.match(growthBlocker("hooks", " ", " ") ?? "", /tema o el guion/);
  assert.equal(growthBlocker("hooks", "tema", ""), null);
  assert.equal(growthBlocker("score", "", "Un guion."), null);
});

test("el puntaje se pinta por tramos", () => {
  assert.deepEqual([20, 49, 50, 74, 75, 100].map(scoreTone), ["bad", "bad", "mid", "mid", "good", "good"]);
});

test("un consejo con mala forma se rechaza", () => {
  assert.throws(() => readGrowth("hooks", {}), /vacío/);
  assert.throws(() => readGrowth("titles", { result: { hooks: [] } }), /incompleto/);
  const ok = readGrowth("titles", { result: { titles: [{ text: "A", score: 80, why: "x" }] } });
  assert.equal(ok.titles[0].text, "A");
});

test("el gancho pasa a ser la primera frase y no se apila con el anterior", () => {
  assert.equal(withHook("Hola mundo.", "¿Sabías esto?"), "¿Sabías esto? Hola mundo.");
  const first = withHook("Hola mundo.", "¿Sabías esto?");
  assert.equal(withHook(first, "Nadie lo cuenta.", "¿Sabías esto?"), "Nadie lo cuenta. Hola mundo.");
  assert.equal(withHook("", "Solo."), "Solo.");
});
