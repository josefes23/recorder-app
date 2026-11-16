#!/usr/bin/env bash
#
#   ./run.sh          Interfaz compilada + API en un solo proceso → :8000
#   ./run.sh --dev     Next con recarga en caliente → :3000, API → :8000
#
# Atajo para Mac y Linux. La lógica está en run.py, que también anda en
# Windows (`py run.py`), así que los dos arrancan igual.
set -euo pipefail
cd "$(dirname "$0")"

PY=./.venv/bin/python
[[ -x "$PY" ]] || PY=python3   # sin entorno todavía: run.py explica qué falta
exec "$PY" run.py "$@"
