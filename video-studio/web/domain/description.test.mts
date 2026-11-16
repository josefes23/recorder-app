import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DESCRIPTION_LIMIT,
  VISIBLE_CHARS,
  descriptionLength,
  platformWarning,
  readDescription,
  visiblePart,
} from "./description.ts";

test("el tope es el de YouTube y las demás plataformas solo se avisan", () => {
  assert.equal(DESCRIPTION_LIMIT, 5000);
  assert.equal(platformWarning("x".repeat(2200)), null);
  assert.match(platformWarning("x".repeat(2201)) ?? "", /Instagram la corta a 2200/);
  assert.match(platformWarning("x".repeat(4001)) ?? "", /TikTok la corta a 4000/);
  assert.equal(descriptionLength("  hola  "), 4);
});

test("lo que se ve antes de «más» se corta por palabra entera", () => {
  assert.equal(visiblePart("  Corta\n\n#tag  "), "Corta #tag");
  const long = "palabra ".repeat(40);
  const visible = visiblePart(long);
  assert.ok(visible.endsWith("palabra…"));
  assert.ok(visible.length <= VISIBLE_CHARS + 1);
  assert.equal(visiblePart(""), "");
});

test("la descripción que llega se comprueba", () => {
  assert.equal(readDescription({ description: "Texto" }), "Texto");
  assert.throws(() => readDescription({ description: "  " }), /vacía/);
  assert.throws(() => readDescription({}), /vacía/);
});
