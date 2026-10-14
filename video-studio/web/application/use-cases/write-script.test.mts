import assert from "node:assert/strict";
import { test } from "node:test";

import type { JobTracker, StudioGateway } from "../ports.ts";
import { writeScript } from "./write-script.ts";

/** Dobles de los puertos: el caso de uso no sabe si detrás hay HTTP o no. */
function fakes(overrides: Partial<StudioGateway> = {}) {
  const calls: string[] = [];
  const gateway = {
    requestScript: async (topic: string) => {
      calls.push(`requestScript:${topic}`);
      return { job: "sc-1", offset: 7 };
    },
    templateScript: async (topic: string) => {
      calls.push(`templateScript:${topic}`);
      return { script: "guion de plantilla", seconds: 30 };
    },
    ...overrides,
  } as unknown as StudioGateway;
  return { gateway, calls };
}

const tracker = (result: Record<string, unknown>): JobTracker => ({
  waitFor: async () => result,
});

test("sin tema no se llama a nadie", async () => {
  const { gateway, calls } = fakes();
  await assert.rejects(
    writeScript(gateway, tracker({}), { topic: "   ", notes: "", useTemplate: false }),
    /Escribe primero un tema/,
  );
  assert.deepEqual(calls, []);
});

test("la plantilla se resuelve en la misma petición, sin esperar eventos", async () => {
  const { gateway, calls } = fakes();
  const jobs: JobTracker = {
    waitFor: async () => assert.fail("la plantilla no debería esperar ningún trabajo"),
  };

  const script = await writeScript(gateway, jobs, {
    topic: "  dormir mejor  ",
    notes: "",
    useTemplate: true,
  });

  assert.equal(script, "guion de plantilla");
  assert.deepEqual(calls, ["templateScript:dormir mejor"]);
});

test("el modelo encola y el guion llega por el trabajo", async () => {
  const { gateway, calls } = fakes();

  const script = await writeScript(gateway, tracker({ script: "guion del modelo", seconds: 31 }), {
    topic: "dormir mejor",
    notes: "tono directo",
    useTemplate: false,
  });

  assert.equal(script, "guion del modelo");
  assert.deepEqual(calls, ["requestScript:dormir mejor"]);
});

test("un trabajo que falla propaga su motivo", async () => {
  const { gateway } = fakes();
  const jobs: JobTracker = {
    waitFor: async () => {
      throw new Error("El modelo tardó demasiado.");
    },
  };

  await assert.rejects(
    writeScript(gateway, jobs, { topic: "dormir mejor", notes: "", useTemplate: false }),
    /El modelo tardó demasiado/,
  );
});

test("un guion vacío no se da por bueno", async () => {
  const { gateway } = fakes();
  await assert.rejects(
    writeScript(gateway, tracker({ script: "   " }), {
      topic: "dormir mejor",
      notes: "",
      useTemplate: false,
    }),
    /llegó vacío/,
  );
});
