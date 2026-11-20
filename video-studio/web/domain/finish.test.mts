import assert from "node:assert/strict";
import { test } from "node:test";

import { cardsSeconds, colorActive, DEFAULT_FINISH, finishSummary, readFinish } from "./finish.ts";
import { DEFAULT_PRODUCTION, forServer, splitStoredStyle } from "./production.ts";

test("sin tocar nada no hay retoques", () => {
  assert.deepEqual(finishSummary(DEFAULT_FINISH), []);
  assert.equal(colorActive(DEFAULT_FINISH.color), false);
  assert.equal(cardsSeconds(DEFAULT_FINISH.cards), 0);
});

test("lo guardado se lee entero y lo que no vale se ignora", () => {
  const read = readFinish({
    audio: { normalize: true, clean: "sí" },
    color: { look: "sepia", exposure: 9, contrast: -0.254, saturation: "x" },
    pace: { tighten: true },
    cards: { intro: "  Lo  que *nadie*  dice ", outro: "x".repeat(500) },
  });
  assert.deepEqual(read.audio, { clean: false, normalize: true });
  assert.deepEqual(read.color, { look: "none", exposure: 1, contrast: -0.25, saturation: 0 });
  assert.equal(read.pace.tighten, true);
  assert.equal(read.cards.intro, "Lo que *nadie* dice");
  assert.equal(read.cards.outro.length, 120);
});

test("un video de antes, o basura, sale sin retoques", () => {
  for (const raw of [undefined, null, "hola", 3, [], {}]) assert.deepEqual(readFinish(raw), DEFAULT_FINISH);
});

test("el resumen dice qué retoques hay y las tarjetas alargan el video", () => {
  const finish = readFinish({
    audio: { normalize: true },
    color: { look: "cine" },
    pace: { tighten: true },
    cards: { intro: "Hola", outro: "Chau" },
  });
  assert.deepEqual(finishSummary(finish), ["audio", "color", "ritmo", "tarjetas"]);
  assert.ok(cardsSeconds(finish.cards) > 4);
  assert.ok(cardsSeconds(readFinish({ cards: { intro: "Hola" } }).cards) < cardsSeconds(finish.cards));
});

test("viaja al servidor y vuelve igual al reutilizar un video", () => {
  const finish = readFinish({ audio: { clean: true }, color: { look: "warm", exposure: 0.3 }, pace: { tighten: true } });
  const sent = forServer({ ...DEFAULT_PRODUCTION, finish });
  assert.deepEqual(sent.finish, finish);
  const stored = splitStoredStyle({ font_size: 90, production: sent });
  assert.deepEqual(stored.production.finish, finish);
  assert.deepEqual(splitStoredStyle({ font_size: 90 }).production.finish, DEFAULT_FINISH);
});
