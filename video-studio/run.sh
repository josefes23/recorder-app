#!/usr/bin/env bash
#
#   ./run.sh          Interfaz compilada + API en un solo proceso → :8000
#   ./run.sh --dev     Next con recarga en caliente → :3000, API → :8000
#
# El modo --dev equivale a `cd web && npm run dev`; está aquí para no tener que
# recordar desde qué carpeta se arranca cada cosa.
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" == "--dev" ]]; then
  echo "Interfaz en http://127.0.0.1:3000 · API en http://127.0.0.1:8000"
  exec npm --prefix web run dev
fi

if [[ ! -d web/out ]]; then
  echo "No hay interfaz compilada todavía. Compilando…"
  npm --prefix web run export
fi

echo "http://127.0.0.1:8000"
exec ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 "$@"
