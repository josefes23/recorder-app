/**
 * Levanta la API (FastAPI) con el Python del entorno de video-studio.
 *
 *   node scripts/api.mjs [--reload] [más opciones de uvicorn]
 *
 * Reemplaza a `cd .. && ./.venv/bin/uvicorn …`, que no anda en Windows: ahí
 * cmd.exe no entiende `./` y el entorno guarda los ejecutables en .venv\Scripts.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const python = fileURLToPath(
  new URL(
    process.platform === "win32" ? "../../.venv/Scripts/python.exe" : "../../.venv/bin/python",
    import.meta.url,
  ),
);

if (!existsSync(python)) {
  console.error(`No encuentro ${python}. Creá el entorno de video-studio primero (ver README).`);
  process.exit(1);
}

const args = ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", ...process.argv.slice(2)];
const child = spawn(python, args, { cwd: root, stdio: "inherit" });

// Ctrl+C le llega también a uvicorn, que está en la misma terminal: acá solo
// se espera a que cierre. Un SIGTERM dirigido (concurrently -k) sí se reenvía.
process.on("SIGINT", () => {});
process.on("SIGTERM", () => child.kill("SIGTERM"));
child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
