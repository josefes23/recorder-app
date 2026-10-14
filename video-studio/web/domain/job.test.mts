import assert from "node:assert/strict";
import { test } from "node:test";

import { failureDetail, outcomeOf } from "./job.ts";

test("solo cierran el trabajo los temas terminales", () => {
  assert.equal(outcomeOf("script.completed"), "completed");
  assert.equal(outcomeOf("script.failed"), "failed");
  assert.equal(outcomeOf("script.requested"), "pending");
  // Un tipo de trabajo nuevo hereda la convención sin tocar nada
  assert.equal(outcomeOf("render.completed"), "completed");
  assert.equal(outcomeOf("render.progress"), "pending");
});

test("el detalle del fallo viaja tal cual, con respaldo si no vino", () => {
  assert.equal(failureDetail({ detail: "La API key no es válida." }), "La API key no es válida.");
  assert.equal(failureDetail({}), "El trabajo falló.");
  assert.equal(failureDetail({ detail: "   " }), "El trabajo falló.");
  assert.equal(failureDetail({ detail: 42 }), "El trabajo falló.");
});
