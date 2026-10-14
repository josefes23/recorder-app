@AGENTS.md

## Solo Claude Code

- `/grabar-demo` y `/corregir-demo` viven en `.claude/skills/`: son el mismo
  flujo que usan Codex y Copilot, así que cualquier cambio ahí vale para los tres.
- `.claude/settings.json` permite `uv run grabar.py` sin pedir permiso y
  bloquea la lectura de `.env`.
