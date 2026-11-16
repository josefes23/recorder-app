import assert from "node:assert/strict";
import { test } from "node:test";

import { assignVoices, guessVoiceGender, speakersIn } from "./dialogue.ts";

const VOICES = [
  { id: "dalia", label: "Dalia — México ♀" },
  { id: "jorge", label: "Jorge — México ♂" },
  { id: "elena", label: "Elena — Argentina ♀" },
];

test("encuentra los personajes en orden, sin el narrador ni etiquetas vacías", () => {
  const script = "NARRADOR: Era de noche.\nANA: ¿Oíste?\nPEDRO: No.\nANA: Otra vez.\nLUIS:\nsin etiqueta";
  assert.deepEqual(speakersIn(script), ["ANA", "PEDRO"]);
  assert.deepEqual(speakersIn("Un reel sin diálogos."), []);
  assert.deepEqual(speakersIn("ana: minúsculas no cuentan"), []);
});

test("da a cada personaje una voz distinta de la del narrador, y que encaje con su nombre", () => {
  assert.deepEqual(assignVoices(["ANA", "PEDRO"], VOICES, "dalia"), { ANA: "elena", PEDRO: "jorge" });
  assert.equal(guessVoiceGender("DOÑA ROSA"), "♀");
  assert.equal(guessVoiceGender("DON PEDRO"), "♂");
});

test("respeta lo que ya se eligió y no repite esa voz", () => {
  const voices = assignVoices(["ANA", "PEDRO"], VOICES, "dalia", { ANA: "jorge" });
  assert.deepEqual(voices, { ANA: "jorge", PEDRO: "elena" });
});

test("con más personajes que voces, las repite", () => {
  const voices = assignVoices(["LUIS", "PEDRO", "JUAN"], VOICES, "dalia");
  assert.deepEqual(voices, { LUIS: "jorge", PEDRO: "elena", JUAN: "jorge" });
});

test("sin etiquetas queda lo que se oye", async () => {
  const { withoutLabels } = await import("./dialogue.ts");
  assert.equal(withoutLabels("NARRADOR: Era de noche.\nANA: ¿Oíste?\nsin etiqueta"), "Era de noche.\n¿Oíste?\nsin etiqueta");
});
