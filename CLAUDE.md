# app-demo-recorder

Grabador de demos de la PWA para la landing, usado por un equipo en Windows,
Linux y Mac. Flujo completo en `.claude/skills/grabar-demo/SKILL.md`; API de
escenas en `recorder/demo.py` y `docs/escribir-escenas.md`.

- Se ejecuta siempre con `uv run` (`uv run grabar.py …`, `uv run instalar.py`):
  nunca `.venv/bin/python` ni el python del sistema.
- Multiplataforma: rutas con `pathlib`, nada de `/tmp`, `killpg` sin
  alternativa para Windows ni comandos que solo existan en bash. Todo
  `read_text`/`write_text`/`subprocess` de texto con `encoding="utf-8"`.
- `config.py` es compartido (va a git). Lo personal (credenciales, `APP_URL`,
  `APP_DIR`) va solo en `.env`: no lo leas ni lo imprimas, y nunca pongas
  credenciales en config.py, escenas ni logs.
- Independiente: no depende de otros proyectos. La voz y el agrupado de
  subtítulos están adaptados de auto-video-generator en `recorder/voice.py` y
  `recorder/subtitles.py`.
- Las escenas usan siempre los métodos de `d.` (no `d.page.click` directo),
  salvo en `prepare()`, que corre fuera de cámara.
- Verificá los videos mirando cuadros antes de dar una tarea por terminada.
- Los videos (`salida/`) no van a git.
