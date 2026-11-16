import assert from "node:assert/strict";
import { test } from "node:test";

import { assignVoices, speakersIn } from "./dialogue.ts";

const VOICES = [
  { id: "dalia", label: "Dalia" },
  { id: "jorge", label: "Jorge" },
  { id: "elena", label: "Elena" },
];

test("encuentra los personajes en orden, sin el narrador ni etiquetas vacías", () => {
  const script = "NARRADOR: Era de noche.\nANA: ¿Oíste?\nPEDRO: No.\nANA: Otra vez.\nLUIS:\nsin etiqueta";
  assert.deepEqual(speakersIn(script), ["ANA", "PEDRO"]);
  assert.deepEqual(speakersIn("Un reel sin diálogos."), []);
  assert.deepEqual(speakersIn("ana: minúsculas no cuentan"), []);
});

test("da a cada personaje una voz distinta de la del narrador", () => {
  assert.deepEqual(assignVoices(["ANA", "PEDRO"], VOICES, "dalia"), { ANA: "jorge", PEDRO: "elena" });
});

test("respeta lo que ya se eligió y no repite esa voz", () => {
  const voices = assignVoices(["ANA", "PEDRO"], VOICES, "dalia", { PEDRO: "jorge" });
  assert.deepEqual(voices, { ANA: "elena", PEDRO: "jorge" });
});

test("con más personajes que voces, las repite", () => {
  const voices = assignVoices(["A", "B", "C"], VOICES, "dalia");
  assert.deepEqual(voices, { A: "jorge", B: "elena", C: "jorge" });
});
