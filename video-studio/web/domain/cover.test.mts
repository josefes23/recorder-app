import assert from "node:assert/strict";
import { test } from "node:test";

import {
  coverCandidates,
  coverImagePrompt,
  coverFilename,
  defaultTitle,
  firstBackground,
  plainTitle,
  readCover,
  readTitles,
  resolveCover,
  titleParts,
  titleWords,
} from "./cover.ts";

test("el título por defecto resalta la palabra más larga del tema, como el servidor", () => {
  assert.equal(defaultTitle("los beneficios del ayuno"), "los *beneficios* del ayuno");
  assert.equal(defaultTitle("¿Por qué el café?"), "¿Por qué el *café?*");
  assert.equal(defaultTitle("el sol"), "el sol");
  assert.equal(defaultTitle("ya *marcado* aquí"), "ya *marcado* aquí");
  assert.equal(defaultTitle("  «Ayuno   real».  "), "*Ayuno* real");
  assert.equal(defaultTitle("   "), "");
});

test("lo que va entre asteriscos resalta; un asterisco suelto se descarta", () => {
  assert.deepEqual(titleParts("El *error* fatal"), [
    { text: "El", highlighted: false },
    { text: "error", highlighted: true },
    { text: "fatal", highlighted: false },
  ]);
  assert.deepEqual(
    titleParts("El *mejor truco* del *año").map((p) => p.highlighted),
    [false, true, true, false, false],
  );
  assert.deepEqual(titleParts("Lo llamó *Padre*, no juez").map((p) => [p.text, p.highlighted]), [
    ["Lo", false], ["llamó", false], ["Padre,", true], ["no", false], ["juez", false],
  ]);
  assert.equal(plainTitle(" El *error*  fatal "), "El error fatal");
  assert.equal(titleWords("El *error* que todos cometen"), 5);
  assert.equal(titleWords(" ** "), 0);
});

test("la portada usa la primera escena con imagen, o el primer clip", () => {
  const scenes = [
    { background: "rio.mp4", start: 0 },
    { background: null, start: 4 },
    { background: "ia-2.jpg", start: 8 },
    { background: "rio.mp4", start: 12 },
  ];
  assert.deepEqual(coverCandidates(scenes), ["rio.mp4", "ia-2.jpg"]);
  assert.equal(firstBackground(scenes), "ia-2.jpg");
  assert.equal(firstBackground([{ background: "rio.mp4", start: 0 }]), "rio.mp4");
  assert.equal(firstBackground([]), null);
});

test("la portada guardada se lee con tolerancia; las de antes no tienen", () => {
  assert.deepEqual(readCover({ title: "Hola", design: "franja", background: "a.jpg" }), {
    title: "Hola", design: "franja", background: "a.jpg",
  });
  assert.deepEqual(readCover({ title: "Hola", design: "neón", background: "" }), {
    title: "Hola", design: "impacto", background: null,
  });
  assert.equal(readCover({}), null);
  assert.equal(readCover(null), null);
  assert.equal(readCover({ title: " * " }), null);
});

test("los títulos que llegan se comprueban", () => {
  assert.deepEqual(readTitles({ titles: ["Uno *más*", 3, " ", "Dos"] }), ["Uno *más*", "Dos"]);
  assert.throws(() => readTitles({ titles: [] }), /no propuso títulos/);
  assert.throws(() => readTitles({}), /no propuso títulos/);
});

test("el archivo se llama como lo llama el servidor", () => {
  assert.equal(coverFilename("¡Ayuno 101!"), "portada-ayuno-101.jpg");
  assert.equal(coverFilename("   "), "portada-video.jpg");
});

test("lo automático sigue al tema y a las escenas hasta que el usuario lo toca", () => {
  const auto = { title: null, design: "franja" as const, background: null };
  assert.deepEqual(resolveCover(auto, "ayuno intermitente", "ia-1.jpg"), {
    title: "ayuno *intermitente*", design: "franja", background: "ia-1.jpg",
  });
  assert.deepEqual(resolveCover({ ...auto, title: "Mío", background: "otra.jpg" }, "x", "ia-1.jpg"), {
    title: "Mío", design: "franja", background: "otra.jpg",
  });
  assert.equal(resolveCover(auto, "  ", "ia-1.jpg"), null);
  assert.equal(resolveCover({ ...auto, title: " ** " }, "tema", null), null);
});

test("el encargo de la imagen de portada parte del tema y de la escena", () => {
  assert.equal(
    coverImagePrompt(" ayuno ", "Una mujer mira el reloj"),
    "Imagen de portada para un video corto sobre «ayuno». Una mujer mira el reloj. Primer plano expresivo, " +
      "con una emoción intensa en la cara, colores vivos, mucho contraste y un fondo sencillo.",
  );
  assert.ok(coverImagePrompt("", "").startsWith("Imagen de portada para un video corto. Primer plano"));
});
