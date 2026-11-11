import assert from "node:assert/strict";
import { test } from "node:test";

import type { IllustrationRequest, JobTracker, StoryboardRequest, StudioGateway } from "../ports.ts";
import {
  awaitSceneImage,
  planStoryboard,
  readStoryboard,
  requestSceneImage,
  requestSceneImages,
} from "./illustrate-scenes.ts";

const ANA = { name: "Ana", traits: "pelo rojo", kind: "persona" as const, saved: null };
const GUIDE = {
  look: " acuarela ",
  characters: [ANA],
  seed: 7,
};
const INPUT = { topic: " Café ", guide: GUIDE, provider: "cloudflare", model: "m", review: true };

const STORYBOARD = {
  guide: { look: "acuarela cálida", characters: [ANA], seed: 7 },
  scenes: [
    { start: 0, text: "Primera frase.", description: "Ana abre la cafetería" },
    { start: 6.2, text: "Segunda frase.", description: "Ana sirve un café" },
  ],
};

/** Dobles del gateway: el caso de uso no sabe si detrás hay HTTP o no. */
function fakes(refuseFrom = Infinity) {
  const requests: IllustrationRequest[] = [];
  const storyboards: StoryboardRequest[] = [];
  const gateway = {
    requestStoryboard: async (request: StoryboardRequest) => {
      storyboards.push(request);
      return { job: "sb-1", offset: 1 };
    },
    requestIllustration: async (request: IllustrationRequest) => {
      if (requests.length >= refuseFrom) throw new Error("A Cloudflare le falta el token.");
      requests.push(request);
      return { job: `im-${requests.length}`, offset: requests.length };
    },
  } as unknown as StudioGateway;
  return { gateway, requests, storyboards };
}

const tracker = (payload: Record<string, unknown>): JobTracker => ({ waitFor: async () => payload });

test("el guion visual se pide con tema, guion y estilo, y se espera por el flujo de eventos", async () => {
  const { gateway, storyboards } = fakes();
  const board = await planStoryboard(gateway, tracker(STORYBOARD), {
    topic: " Café ",
    script: "Primera frase. Segunda frase.",
    style: " acuarela ",
    // La fila a medio rellenar no viaja.
    characters: [ANA, { name: "", traits: "", kind: "persona", saved: null }],
  });
  assert.deepEqual(storyboards, [
    { topic: "Café", script: "Primera frase. Segunda frase.", style: "acuarela", characters: [ANA] },
  ]);
  assert.deepEqual(board, STORYBOARD);

  await assert.rejects(
    planStoryboard(gateway, tracker(STORYBOARD), { topic: "t", script: "  ", style: "", characters: [] }),
    /Escribe primero el guion/,
  );
  assert.equal(storyboards.length, 1);
});

test("un guion visual roto se rechaza, y lo que sobra o falta se normaliza", () => {
  assert.throws(() => readStoryboard({}), /llegó vacío/);
  assert.throws(() => readStoryboard({ guide: { look: "x" }, scenes: [] }), /llegó vacío/);
  const board = readStoryboard({
    guide: {
      look: "x",
      characters: [
        { name: "Ana" },
        { name: "Eva", traits: "rubia" },
        { name: "Rex", traits: "perro", kind: "animal", saved: 4 },
        { name: "Mesa", traits: "roble", kind: "dragón", saved: "2" },
      ],
    },
    scenes: [{ description: "algo" }],
  });
  assert.deepEqual(board.guide, {
    look: "x",
    characters: [
      { name: "Eva", traits: "rubia", kind: "persona", saved: null },
      { name: "Rex", traits: "perro", kind: "animal", saved: 4 },
      { name: "Mesa", traits: "roble", kind: "persona", saved: null },
    ],
    seed: null,
  });
  assert.deepEqual(board.scenes, [{ start: 0, text: "", description: "algo" }]);
});

test("pide una imagen por escena, todas con la misma guía, y avisa de cada encargo", async () => {
  const { gateway, requests } = fakes();
  const seen: Array<[number, string]> = [];
  await requestSceneImages(gateway, [" Ana abre ", "Ana sirve"], INPUT, (i, job) => seen.push([i, job]));

  assert.deepEqual(seen, [[0, "im-1"], [1, "im-2"]]);
  assert.deepEqual(requests[0], {
    topic: "Café",
    description: "Ana abre",
    look: "acuarela",
    characters: [ANA],
    seed: 7,
    provider: "cloudflare",
    model: "m",
    review: true,
  });
  assert.equal(requests[1].seed, 7);
});

test("un rechazo corta el resto de encargos", async () => {
  const { gateway, requests } = fakes(1);
  const seen: number[] = [];
  await assert.rejects(
    requestSceneImages(gateway, ["uno", "dos", "tres"], INPUT, (i) => seen.push(i)),
    /le falta el token/,
  );
  assert.deepEqual(seen, [0]);
  assert.equal(requests.length, 1);
});

test("una imagen suelta exige descripción", async () => {
  const { gateway, requests } = fakes();
  await assert.rejects(requestSceneImage(gateway, "  ", INPUT), /Describe qué debe mostrar/);
  assert.equal(await requestSceneImage(gateway, "  una taza  ", INPUT), "im-1");
  assert.equal(requests[0].description, "una taza");
  assert.equal(requests[0].look, "acuarela");
});

test("la imagen terminada devuelve su nombre en la galería y lo que dijo el revisor", async () => {
  assert.deepEqual(await awaitSceneImage(tracker({ name: "ia-cafe_1.jpg", review: null }), "im-1"), {
    name: "ia-cafe_1.jpg",
    review: null,
  });
  const review = { status: "approved", reviewer: "Claude", attempts: 2, problems: [], fixed: ["tres brazos"], detail: "" };
  assert.deepEqual((await awaitSceneImage(tracker({ name: "ia.jpg", review }), "im-1")).review, review);
  await assert.rejects(awaitSceneImage(tracker({}), "im-1"), /sin nombre/);
});

test("sin revisión, el encargo lo dice", async () => {
  const { gateway, requests } = fakes();
  await requestSceneImage(gateway, "una taza", { ...INPUT, review: false });
  assert.equal(requests[0].review, false);
});
