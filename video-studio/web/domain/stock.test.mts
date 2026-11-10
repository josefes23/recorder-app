import assert from "node:assert/strict";
import { test } from "node:test";

import { describeDownload, markOwned, releaseOwned, type StockClip } from "./stock.ts";

const clip = (id: number, owned = false): StockClip => ({
  id,
  preview: "",
  duration: 10,
  width: 1080,
  height: 1920,
  size_mb: 3,
  author: "Ana",
  url: "",
  play: "",
  name: `mar_${id}.mp4`,
  owned,
});

test("el resumen cuenta nuevos, repetidos y fallos, en singular o plural", () => {
  assert.equal(describeDownload({ added: ["a"], existing: [], failed: [] }), "1 clip nuevo");
  assert.equal(
    describeDownload({ added: ["a", "b"], existing: ["c"], failed: ["d: sin red"] }),
    "2 clips nuevos · 1 ya estaba · falló d: sin red",
  );
  assert.equal(describeDownload({ added: [], existing: ["c", "d"], failed: [] }), "2 ya estaban");
});

test("tras descargar, los clips que entraron quedan como de la galería", () => {
  const marked = markOwned([clip(1), clip(2), clip(3, true)], {
    added: ["mar_1.mp4"],
    existing: ["mar_3.mp4"],
    failed: ["mar_2.mp4: sin red"],
  });
  assert.deepEqual(
    marked.map((c) => c.owned),
    [true, false, true],
  );
});

test("al borrar un fondo de la galería, su clip deja de contar como descargado", () => {
  const released = releaseOwned([clip(1, true), clip(2, true)], "mar_2.mp4");
  assert.deepEqual(
    released.map((c) => c.owned),
    [true, false],
  );
});
