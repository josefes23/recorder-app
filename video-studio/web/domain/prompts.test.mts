import assert from "node:assert/strict";
import { test } from "node:test";

import { byGroup, editedCount, type PromptInfo } from "./prompts.ts";

const make = (id: string, group: PromptInfo["group"], edited = false): PromptInfo => ({
  id, name: id, group, when: "", user_part: "", variables: [], default: "", text: "", edited, examples: [], warnings: [],
});

test("los prompts se agrupan por modelo y se cuentan los editados", () => {
  const all = [make("a", "imagen", true), make("b", "texto"), make("c", "imagen")];
  assert.deepEqual(byGroup(all).map((g) => [g.group, g.items.length]), [["texto", 1], ["imagen", 2]]);
  assert.equal(editedCount(all), 1);
});
