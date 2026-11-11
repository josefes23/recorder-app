import assert from "node:assert/strict";
import { test } from "node:test";

import type { CharacterSaveRequest, JobTracker, ReferenceRequest, StudioGateway } from "../ports.ts";
import { awaitReference, repaintReference, saveToLibrary } from "./character-library.ts";

const PINCEL = { name: " Pincel ", traits: " robot naranja ", kind: "objeto" as const, saved: null };
const CHOICE = { provider: "cloudflare", model: "m" };

function fakes() {
  const saves: CharacterSaveRequest[] = [];
  const repaints: Array<[number, ReferenceRequest]> = [];
  const gateway = {
    saveCharacter: async (request: CharacterSaveRequest) => {
      saves.push(request);
      return {
        character: { id: 1, name: "Pincel", traits: "robot naranja", kind: "objeto", reference: null, created_at: "", updated_at: "" },
        job: "rf-1",
      };
    },
    repaintReference: async (id: number, request: ReferenceRequest) => {
      repaints.push([id, request]);
      return { job: "rf-2", offset: 2 };
    },
  } as unknown as StudioGateway;
  return { gateway, saves, repaints };
}

test("guardar en la biblioteca manda el elemento limpio y el estilo del video", async () => {
  const { gateway, saves } = fakes();
  const { character, job } = await saveToLibrary(gateway, PINCEL, " acuarela ", CHOICE);
  assert.equal(job, "rf-1");
  assert.equal(character.id, 1);
  assert.deepEqual(saves, [
    { name: "Pincel", traits: "robot naranja", kind: "objeto", look: "acuarela", provider: "cloudflare", model: "m" },
  ]);
  await assert.rejects(saveToLibrary(gateway, { ...PINCEL, traits: " " }, "", CHOICE), /nombre y rasgos/);
  assert.equal(saves.length, 1);
});

test("sin generador elegido, decide el servidor", async () => {
  const { gateway, saves, repaints } = fakes();
  await saveToLibrary(gateway, PINCEL, "", null);
  assert.equal(saves[0].provider, "");
  assert.equal(await repaintReference(gateway, 1, " óleo ", null), "rf-2");
  assert.deepEqual(repaints, [[1, { look: "óleo", provider: "", model: "" }]]);
});

test("la referencia terminada trae su archivo; sin él, es un error", async () => {
  const tracker = (payload: Record<string, unknown>): JobTracker => ({ waitFor: async () => payload });
  assert.deepEqual(await awaitReference(tracker({ reference: "ref-1.jpg", review: null }), "rf-1"), {
    reference: "ref-1.jpg",
    review: null,
  });
  await assert.rejects(awaitReference(tracker({}), "rf-1"), /llegó vacía/);
});
