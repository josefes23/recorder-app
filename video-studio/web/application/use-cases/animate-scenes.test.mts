import assert from "node:assert/strict";
import { test } from "node:test";

import type { AnimationRequest, JobTracker, StudioGateway, WaitOptions } from "../ports.ts";
import { ANIMATION_GIVE_UP_MS, awaitSceneClip, requestSceneAnimation } from "./animate-scenes.ts";

const ANA = { name: "Ana", traits: "pelo rojo", kind: "persona" as const, saved: null };
const EMPTY = { name: "", traits: "", kind: "persona" as const, saved: null };
const INPUT = { topic: " Café ", guide: { look: " acuarela ", characters: [ANA, EMPTY], seed: 7 } };

function fakeGateway() {
  const requests: AnimationRequest[] = [];
  const gateway = {
    requestAnimation: async (request: AnimationRequest) => {
      requests.push(request);
      return { job: "an-1", offset: 3 };
    },
  } as unknown as StudioGateway;
  return { gateway, requests };
}

test("pide el clip del largo del tramo, con la guía del video", async () => {
  const { gateway, requests } = fakeGateway();
  const job = await requestSceneAnimation(
    gateway,
    { source: "ia-cafe_1.jpg", description: " Ana sirve un café ", span: 6.2 },
    INPUT,
  );

  assert.equal(job, "an-1");
  assert.deepEqual(requests[0], {
    topic: "Café",
    source: "ia-cafe_1.jpg",
    seconds: 7,
    description: "Ana sirve un café",
    look: "acuarela",
    // Las filas a medio rellenar no viajan: el servidor las rechazaría.
    characters: [ANA],
    seed: 7,
    format: "9:16",
  });
});

test("sin imagen no pide nada", async () => {
  const { gateway, requests } = fakeGateway();
  await assert.rejects(
    requestSceneAnimation(gateway, { source: "", description: "", span: 6 }, INPUT),
    /no tiene imagen/,
  );
  assert.equal(requests.length, 0);
});

test("espera el clip con un plantón largo y devuelve su nombre", async () => {
  const waits: (WaitOptions | undefined)[] = [];
  const jobs: JobTracker = {
    waitFor: async (_job, options) => {
      waits.push(options);
      return { name: "ia-cafe_1-mov-a1b2c3.mp4" };
    },
  };
  assert.equal(await awaitSceneClip(jobs, "an-1"), "ia-cafe_1-mov-a1b2c3.mp4");
  assert.deepEqual(waits, [{ giveUpMs: ANIMATION_GIVE_UP_MS }]);

  const empty: JobTracker = { waitFor: async () => ({}) };
  await assert.rejects(awaitSceneClip(empty, "an-2"), /sin nombre/);
});

test("un video horizontal pide el clip horizontal", async () => {
  const { gateway, requests } = fakeGateway();
  await requestSceneAnimation(gateway, { source: "a.jpg", description: "", span: 4 }, { ...INPUT, format: "16:9" });
  assert.equal(requests[0].format, "16:9");
});
