/**
 * Resuelve el alias `@/` (tsconfig `paths`) cuando las pruebas corren con
 * `node --test`, sin bundler de por medio.
 *
 * Node borra los `import type`, así que mientras un caso de uso solo traía
 * tipos de `@/domain/…` daba igual; en cuanto importa una función (leer una
 * revisión, validar un tipo) necesita encontrar el archivo. El código sigue
 * usando `@/` como el resto del proyecto, y las pruebas lo entienden igual.
 */
import { existsSync } from "node:fs";
import { registerHooks } from "node:module";

const ROOT = new URL("../../", import.meta.url);
const EXTENSIONS = [".ts", ".tsx", "/index.ts"];

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith("@/")) {
      const base = new URL(specifier.slice(2), ROOT).href;
      const found = EXTENSIONS.map((ext) => base + ext).find((url) => existsSync(new URL(url)));
      if (found) return nextResolve(found, context);
    }
    return nextResolve(specifier, context);
  },
});
