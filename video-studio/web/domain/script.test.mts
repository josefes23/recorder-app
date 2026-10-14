import assert from "node:assert/strict";
import { test } from "node:test";

import { countWords, durationVerdict, estimateSeconds, sampleCaption } from "./script.ts";

test("cuenta palabras ignorando espacios de más", () => {
  assert.equal(countWords("  hola   mundo \n cruel "), 3);
  assert.equal(countWords("   "), 0);
});

test("estima segundos al ritmo de las voces en español", () => {
  // 108 palabras a 2,7 por segundo = 40 s, dentro de la horquilla del Reel
  const script = Array.from({ length: 108 }, () => "palabra").join(" ");
  assert.equal(estimateSeconds(script), 40);
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
