import assert from "node:assert/strict";
import { test } from "node:test";

import { assignVoices, guessVoiceGender, speakersIn } from "./dialogue.ts";
import type { Voice } from "./voice.ts";

const VOICES: Voice[] = [
  { id: "dalia", label: "Dalia — México ♀", provider: "edge" },
  { id: "jorge", label: "Jorge — México ♂", provider: "edge" },
  { id: "elena", label: "Elena — Argentina ♀", provider: "edge" },
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

test("la asignación automática nunca elige una voz de ElevenLabs", () => {
  const withEleven: Voice[] = [
    ...VOICES,
    { id: "eleven:abc", label: "Rachel — ElevenLabs", provider: "elevenlabs" },
  ];
  const assigned = assignVoices(["ANA", "LUIS", "SOFI", "PEDRO", "MARTA"], withEleven, "dalia");
  for (const id of Object.values(assigned)) assert.notEqual(id, "eleven:abc");
});

test("una voz de ElevenLabs que el usuario eligió se respeta", () => {
  const withEleven: Voice[] = [...VOICES, { id: "eleven:abc", label: "Rachel — ElevenLabs", provider: "elevenlabs" }];
  assert.equal(assignVoices(["ANA"], withEleven, "dalia", { ANA: "eleven:abc" }).ANA, "eleven:abc");
});
