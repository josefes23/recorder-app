/**
 * `next build` en modo export: la interfaz estática en web/out, que sirve FastAPI.
 *
 * Reemplaza a `NEXT_EXPORT=1 next build`. Esa forma de pasar una variable es
 * de bash y cmd.exe (Windows) no la entiende. Se llama al CLI de Next con el
 * mismo Node, sin shell de por medio, así que anda igual en los tres sistemas.
 */
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";

const next = createRequire(import.meta.url).resolve("next/dist/bin/next");
const result = spawnSync(process.execPath, [next, "build", ...process.argv.slice(2)], {
  stdio: "inherit",
  env: { ...process.env, NEXT_EXPORT: "1" },
});
process.exit(result.status ?? 1);
