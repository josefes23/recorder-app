import assert from "node:assert/strict";
import { test } from "node:test";

import { DEFAULT_PRODUCTION, forServer, lengthRange, splitStoredStyle } from "./production.ts";
import { durationVerdict } from "./script.ts";

test("las voces solo viajan con el diálogo activado", () => {
  const production = { ...DEFAULT_PRODUCTION, voices: { ANA: "elena" } };
  assert.deepEqual(forServer(production).voices, {});
  assert.deepEqual(forServer({ ...production, dialogue: true }).voices, { ANA: "elena" });
  assert.equal(forServer(DEFAULT_PRODUCTION).music_volume, 0.25);
  // Hasta que se elija otra, el corte seco de siempre.
  assert.deepEqual(forServer(DEFAULT_PRODUCTION).transition, { kind: "corte", seconds: 0.5 });
});

test("un video guardado se separa en estilo y producción", () => {
  const { style, production } = splitStoredStyle({
    font_size: 64,
    production: {
      format: "16:9", length: "corto", voices: { ANA: "elena", X: 3 }, music: "calma.mp3", music_volume: 0.4, ambient: true,
      transition: { kind: "negro", seconds: 0.8 },
    },
  });
  assert.deepEqual(style, { font_size: 64 });
  assert.deepEqual(production, {
    format: "16:9", length: "corto", dialogue: true, voices: { ANA: "elena" },
    music: "calma.mp3", musicVolume: 0.4, ambient: true, transition: { kind: "negro", seconds: 0.8 },
  });
});

test("uno de antes, sin producción, es un reel vertical con una voz", () => {
  const { style, production } = splitStoredStyle({ font_size: 92 });
  assert.deepEqual(style, { font_size: 92 });
  assert.deepEqual(production, DEFAULT_PRODUCTION);
  assert.deepEqual(splitStoredStyle(undefined).production, DEFAULT_PRODUCTION);
});

test("la duración se juzga con la horquilla de cada formato", () => {
  const twoMinutes = Array.from({ length: 330 }, () => "palabra").join(" ");
  assert.equal(durationVerdict(twoMinutes), "long");
  assert.equal(durationVerdict(twoMinutes, lengthRange("corto")), "ok");
  assert.equal(durationVerdict("hola " .repeat(100), lengthRange("corto")), "short");
});

test("un video guardado recuerda la toma de voz con que se renderizó", async () => {
  const { storedTake } = await import("./production.ts");
  assert.equal(storedTake({ production: { take: "0123456789abcdef" } }), "0123456789abcdef");
  assert.equal(storedTake({ production: { take: "../x" } }), null);
  assert.equal(storedTake({ font_size: 92 }), null); // uno de antes
  assert.equal(storedTake(undefined), null);
});
