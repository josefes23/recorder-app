import assert from "node:assert/strict";
import { test } from "node:test";

import type { StudioGateway } from "../ports.ts";
import { downloadStock, searchStock } from "./manage-backgrounds.ts";

/** Dobles del gateway: el caso de uso no sabe si detrás hay HTTP o no. */
function fakes() {
  const calls: string[] = [];
  const gateway = {
    searchStock: async (query: string) => {
      calls.push(`searchStock:${query}`);
      return [];
    },
    downloadStock: async (query: string, ids: number[]) => {
      calls.push(`downloadStock:${query}:${ids.join(",")}`);
      return { added: [], existing: [], failed: [], items: [] };
    },
  } as unknown as StudioGateway;
  return { gateway, calls };
}

test("buscar recorta la búsqueda y la devuelve junto a los resultados", async () => {
  const { gateway, calls } = fakes();
  await assert.rejects(searchStock(gateway, "   "), /qué clips buscar/);
  assert.deepEqual(await searchStock(gateway, "  mar  "), { query: "mar", clips: [] });
  assert.deepEqual(calls, ["searchStock:mar"]);
});

test("descargar exige al menos un clip marcado", async () => {
  const { gateway, calls } = fakes();
  await assert.rejects(downloadStock(gateway, "mar", []), /al menos un clip/);
  await downloadStock(gateway, "mar", [11, 12]);
  assert.deepEqual(calls, ["downloadStock:mar:11,12"]);
});
