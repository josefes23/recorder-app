import assert from "node:assert/strict";
import { test } from "node:test";

import {
  realStarts,
  roundHalfEven,
  sceneWords,
  spokenAt,
  startForWord,
  takeSignature,
  wordAt,
  type WordMark,
} from "./narration.ts";

const voice = (...marks: [string, number, number][]): WordMark[] =>
  marks.map(([text, start, end]) => ({ text, start, end }));

test("cada escena dice desde su palabra hasta la de la siguiente", () => {
  const script = "**Uno** dos tres. Cuatro cinco seis. Siete ocho nueve.";
  // 1,1 s · 2,7 palabras/s = palabra 3 («Cuatro»); 2,2 s = palabra 6 («Siete»).
  const scenes = [{ background: "a", start: 0 }, { background: "b", start: 1.1 }, { background: "c", start: 2.2 }];
  assert.deepEqual(sceneWords(scenes, script).map((s) => s.text), [
    "Uno dos tres.",
    "Cuatro cinco seis.",
    "Siete ocho nueve.",
  ]);
  // Desordenadas: cada una dice lo suyo igual, y la que entra tras la voz no dice nada.
  const late = [{ background: "a", start: 0 }, { background: "c", start: 2.2 }, { background: "z", start: 60 }];
  assert.deepEqual(sceneWords(late, script).map((s) => s.text), ["Uno dos tres. Cuatro cinco seis.", "Siete ocho nueve.", ""]);
});

test("mover una escena a una palabra la hace entrar justo con ella", () => {
  for (const k of [1, 3, 14, 40, 41, 95, 300]) assert.equal(wordAt(startForWord(k)), k);
  // Los empates, como el round de Python: a la par.
  assert.equal(roundHalfEven(40.5), 40);
  assert.equal(roundHalfEven(13.5), 14);
  assert.equal(roundHalfEven(2.4), 2);
});

test("con la voz, cada escena entra en mitad del silencio que precede a su frase (como el render)", () => {
  const script = "Uno dos tres. Cuatro cinco seis. Siete ocho nueve.";
  const words = voice(
    ["Uno", 0.0, 0.9], ["dos", 1.0, 1.9], ["tres", 2.0, 2.9],
    ["Cuatro", 3.5, 4.4], ["cinco", 4.5, 5.4], ["seis", 5.5, 6.4],
    ["Siete", 7.0, 7.9], ["ocho", 8.0, 8.9], ["nueve", 9.0, 9.9],
  );
  const scenes = [{ background: "a", start: 0 }, { background: "b", start: 1.1 }, { background: "c", start: 2.2 }];
  assert.deepEqual(realStarts(scenes, script, words), [0, 3.2, 6.7]);
});

test("un número que la voz dice con otras palabras corta al acabar la última que casó", () => {
  const script = "Uno dos. 115 años después.";
  const words = voice(
    ["Uno", 0.0, 0.5], ["dos", 0.6, 1.0], ["ciento", 1.5, 1.9],
    ["quince", 2.0, 2.4], ["años", 2.5, 2.9], ["después", 3.0, 3.5],
  );
  assert.deepEqual(realStarts([{ background: "x", start: 0 }, { background: "a", start: 0.7 }], script, words), [0, 1.0]);
});

test("las que entran tras la voz guardan su distancia al final real; sin marcas, nada cambia", () => {
  const script = "Uno dos tres.";
  const words = voice(["Uno", 0.0, 1.0], ["dos", 1.0, 2.0], ["tres", 2.0, 3.0]);
  const scenes = [{ background: "a", start: 0 }, { background: "b", start: 2.0 }];
  assert.deepEqual(realStarts(scenes, script, words), [0, 3.89]);
  assert.deepEqual(realStarts(scenes, script, []), [0, 2.0]);
});

test("el subtítulo de la animática sigue a la voz, en bloques", () => {
  const words = voice(...Array.from({ length: 8 }, (_, i) => [`p${i}`, i, i + 0.8] as [string, number, number]));
  assert.equal(spokenAt(words, -1), "");
  assert.equal(spokenAt(words, 0.5), "p0 p1 p2 p3 p4 p5");
  assert.equal(spokenAt(words, 6.2), "p6 p7");
  assert.equal(spokenAt(words, 20), "");
});

test("una toma vale mientras no cambien el guion ni la voz", () => {
  const input = { script: "Hola", voice: "v", rate: "+8%", pitch: "+0Hz", voices: { ANA: "a", BEA: "b" } };
  assert.equal(takeSignature(input), takeSignature({ ...input, voices: { BEA: "b", ANA: "a" } }));
  assert.notEqual(takeSignature(input), takeSignature({ ...input, rate: "+0%" }));
});

test("una escena se mueve de palabra en palabra sin pisar a sus vecinas", async () => {
  const { movableWords } = await import("./narration.ts");
  const script = "Uno dos tres. Cuatro cinco seis. Siete ocho nueve.";
  const scenes = [{ background: "a", start: 0 }, { background: "b", start: 1.1 }, { background: "c", start: 2.2 }];
  const words = sceneWords(scenes, script);
  assert.equal(movableWords(words, 0, 9), null); // la primera empieza siempre con la primera palabra
  assert.deepEqual(movableWords(words, 1, 9), [1, 5]); // entre «Uno» y «Siete»
  assert.deepEqual(movableWords(words, 2, 9), [4, 8]); // tras «Cuatro», hasta la última
});
