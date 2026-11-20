import assert from "node:assert/strict";
import { test } from "node:test";

import { countWords, durationVerdict, estimateSeconds, sampleCaption } from "./script.ts";

test("cuenta palabras ignorando espacios de más", () => {
  assert.equal(countWords("  hola   mundo \n cruel "), 3);
  assert.equal(countWords("   "), 0);
});

test("estima segundos al ritmo de las voces en español", () => {
  // 135 palabras a 2,7 por segundo = 50 s, dentro de la horquilla del Reel
  const script = Array.from({ length: 135 }, () => "palabra").join(" ");
  assert.equal(estimateSeconds(script), 50);
  assert.equal(durationVerdict(script), "ok");
});

test("avisa cuando el guion se queda corto o se pasa", () => {
  assert.equal(durationVerdict(""), "empty");
  assert.equal(durationVerdict("una frase suelta"), "short");
  assert.equal(durationVerdict(Array.from({ length: 200 }, () => "palabra").join(" ")), "long");
});

test("la muestra del fotograma son las primeras palabras", () => {
  assert.equal(sampleCaption("uno dos tres cuatro cinco seis siete"), "uno dos tres cuatro cinco");
  assert.equal(sampleCaption("   "), "Texto de ejemplo");
});

test("la animática enseña la frase que suena en cada segundo, en bloques", async () => {
  const { wordsAt } = await import("./script.ts");
  const script = "**Uno** dos tres cuatro cinco seis siete ocho nueve diez";
  assert.equal(wordsAt(script, 0), "Uno dos tres cuatro cinco seis");
  assert.equal(wordsAt(script, 2.5), "siete ocho nueve diez"); // 2,5 s · 2,7 palabras/s = palabra 6
  assert.equal(wordsAt(script, 60), "");
});
