import assert from "node:assert/strict";
import { test } from "node:test";

import {
  canSaveImages,
  MAX_CHARACTERS,
  castHas,
  castIn,
  correctionDraft,
  fromSaved,
  libraryState,
  mentioning,
  readSaved,
  suggestionsFor,
  withCharacter,
  choiceFromKey,
  choiceKey,
  defaultChoice,
  isAvailable,
  namesOf,
  readReview,
  readyChoices,
  reviewNote,
  type Character,
  type ImageProvider,
  type SavedCharacter,
  type ImageSettings,
} from "./illustration.ts";

const person = (name: string, traits: string, saved: number | null = null): Character => ({
  name,
  traits,
  kind: "persona",
  saved,
});

const provider = (id: string, ready: boolean, models: string[]): ImageProvider => ({
  id,
  name: id === "google" ? "Google Nano Banana" : "Cloudflare Workers AI",
  note: "",
  ready,
  fields: [{ env: `${id.toUpperCase()}_KEY`, label: "Clave", secret: true, hint: ready ? "…1234" : null }],
  model: models[0],
  models: models.map((m) => ({ id: m, label: m.toUpperCase(), note: "" })),
});

const settings = (chosen: string, cloudflareReady: boolean, googleReady: boolean): ImageSettings => ({
  provider: chosen,
  label: null,
  style: "",
  providers: [provider("cloudflare", cloudflareReady, ["klein4", "klein9"]), provider("google", googleReady, ["nb"])],
});

test("solo se ofrecen los modelos de los generadores listos", () => {
  assert.deepEqual(
    readyChoices(settings("cloudflare", false, true)).map((c) => c.label),
    ["Google · NB"],
  );
  assert.deepEqual(readyChoices(null), []);
});

test("por defecto pinta el elegido si está listo; si no, el primero que lo esté", () => {
  assert.deepEqual(defaultChoice(settings("google", true, true)), { provider: "google", model: "nb" });
  assert.deepEqual(defaultChoice(settings("google", true, false)), { provider: "cloudflare", model: "klein4" });
  assert.equal(defaultChoice(settings("google", false, false)), null);
});

test("una elección deja de valer si su generador ya no está listo", () => {
  const choice = { provider: "cloudflare", model: "klein9" };
  assert.equal(isAvailable(settings("cloudflare", true, false), choice), true);
  assert.equal(isAvailable(settings("cloudflare", false, true), choice), false);
  assert.deepEqual(choiceFromKey(choiceKey({ provider: "cloudflare", model: "@cf/a|b" })), {
    provider: "cloudflare",
    model: "@cf/a|b",
  });
});

test("guardar exige cada dato guardado o escrito", () => {
  const empty = provider("cloudflare", false, ["klein4"]);
  assert.equal(canSaveImages(empty, {}), false);
  assert.equal(canSaveImages(empty, { CLOUDFLARE_KEY: "  " }), false);
  assert.equal(canSaveImages(empty, { CLOUDFLARE_KEY: "tok" }), true);
  assert.equal(canSaveImages(provider("google", true, ["nb"]), {}), true);
});

test("una escena lleva los rasgos de quien nombra, sin mirar tildes ni mayúsculas", () => {
  const jesus = person("Jesús", "túnica crema");
  const juan = person("Juan el Bautista", "piel de camello");
  assert.deepEqual(castIn("JESUS entra al río con Juan el bautista", [jesus, juan]), [jesus, juan]);
  assert.deepEqual(castIn("Juan pesca", [jesus, juan]), []);
  assert.deepEqual(castIn("los jesuitas", [jesus]), []);
  assert.deepEqual(castIn("algo", [person(" ", "x")]), []);
});

test("los nombres se enumeran como se dicen", () => {
  const c = (name: string) => person(name, "");
  assert.equal(namesOf([]), "");
  assert.equal(namesOf([c("Ana")]), "Ana");
  assert.equal(namesOf([c("Ana"), c("Luis"), c("Eva")]), "Ana, Luis y Eva");
});

test("la revisión se lee con cuidado: lo que no encaja se descarta", () => {
  assert.equal(readReview(null), null);
  assert.equal(readReview({ status: "quizá" }), null);
  assert.deepEqual(readReview({ status: "flagged", problems: ["tres brazos", 4], attempts: 0 }), {
    status: "flagged",
    reviewer: "El revisor",
    attempts: 1,
    problems: ["tres brazos"],
    fixed: [],
    detail: "",
  });
});

test("cada revisión se cuenta en una línea, y los fallos van como aviso", () => {
  const base = { reviewer: "Claude", problems: [], fixed: [], detail: "" };
  assert.deepEqual(reviewNote({ ...base, status: "approved", attempts: 1 }), {
    text: "Revisada por Claude.",
    warn: false,
  });
  assert.deepEqual(
    reviewNote({ ...base, status: "approved", attempts: 2, fixed: ["la mujer tiene una tercera mano."] }),
    { text: "Revisada por Claude. Descartó 1 imagen con fallos: la mujer tiene una tercera mano.", warn: false },
  );
  assert.equal(
    reviewNote({ ...base, status: "approved", attempts: 3, fixed: ["a", "b"] }).text,
    "Revisada por Claude. Descartó 2 imágenes con fallos: a; b.",
  );
  assert.deepEqual(reviewNote({ ...base, status: "flagged", attempts: 3, problems: ["tres brazos", "letras"] }), {
    text: "Claude ve fallos tras 3 intentos: tres brazos; letras. Corrígela, pide otra o elige otro fondo.",
    warn: true,
  });
  assert.deepEqual(reviewNote({ ...base, status: "unchecked", attempts: 1, detail: "Límite de peticiones alcanzado." }), {
    text: "Sin revisar: Límite de peticiones alcanzado.",
    warn: true,
  });
});

test("al corregir se parte de los fallos que vio el revisor, si los vio", () => {
  const base = { reviewer: "Claude", attempts: 3, fixed: [], detail: "" };
  assert.equal(
    correctionDraft({ ...base, status: "flagged", problems: ["Ana tiene tres brazos.", "hay letras en el cielo"] }),
    "Ana tiene tres brazos; hay letras en el cielo.",
  );
  assert.equal(correctionDraft({ ...base, status: "approved", problems: [], fixed: ["tres brazos"] }), "");
  assert.equal(correctionDraft({ ...base, status: "flagged", problems: [] }), "");
  assert.equal(correctionDraft(undefined), "");
});

const saved = (id: number, name: string, traits: string, kind: SavedCharacter["kind"] = "persona"): SavedCharacter => ({
  id,
  name,
  traits,
  kind,
  reference: `ref-${id}.jpg`,
  created_at: "",
  updated_at: "2026-11-11T12:00:00",
});

test("frente a la biblioteca, un elemento está sin guardar, guardado o con cambios", () => {
  const library = [saved(1, "Lucía", "mujer de 30 años")];
  assert.equal(libraryState(person("Mateo", "x"), library), "unsaved");
  assert.equal(libraryState(person("lucia", "mujer  de 30 años"), library), "saved");
  assert.equal(libraryState(person("Lucía", "mujer de 40 años"), library), "changed");
  assert.equal(libraryState({ ...person("Lucía", "mujer de 30 años"), kind: "animal" }, library), "changed");
});

test("meter un guardado en el reparto lo pone al día por nombre y respeta el tope", () => {
  const pincel = fromSaved(saved(3, "Pincel", "robot naranja", "objeto"));
  assert.deepEqual(pincel, { name: "Pincel", traits: "robot naranja", kind: "objeto", saved: 3 });
  const cast = [person("Ana", "pelo rojo"), person("pincel", "otro")];
  assert.deepEqual(withCharacter(cast, pincel), [cast[0], pincel]);
  assert.ok(castHas(cast, "PINCEL"));
  const full = Array.from({ length: MAX_CHARACTERS }, (_, i) => person(`P${i}`, "t"));
  assert.equal(withCharacter(full, pincel), full);
});

test("a cada escena se le propone lo del reparto que no nombra y lo guardado que falta", () => {
  const cast = [person("Ana", "pelo rojo"), person("Luis", "barba", 2)];
  const library = [saved(2, "Luis", "barba"), saved(3, "Pincel", "robot", "objeto")];
  assert.deepEqual(
    suggestionsFor("Ana pinta sola", cast, library).map((c) => [c.name, c.saved]),
    [["Luis", 2], ["Pincel", 3]],
  );
  assert.deepEqual(suggestionsFor("Ana y Luis con Pincel", [...cast, fromSaved(library[1])], library), []);
});

test("sumar un elemento a la escena es nombrarlo en la descripción", () => {
  assert.equal(mentioning("Ana pinta en la mesa.", "Pincel"), "Ana pinta en la mesa, con Pincel");
  assert.equal(mentioning("Ana y pincel pintan", "Pincel"), "Ana y pincel pintan");
  assert.equal(mentioning("  ", "Pincel"), "Pincel");
});

test("la biblioteca que llega del servidor se lee con cuidado", () => {
  assert.deepEqual(readSaved(null), []);
  assert.deepEqual(
    readSaved([{ id: 1, name: "Rex", traits: "perro", kind: "dragón" }, { name: "sin id" }, "basura"]),
    [{ id: 1, name: "Rex", traits: "perro", kind: "persona", reference: null, created_at: "", updated_at: "" }],
  );
});

