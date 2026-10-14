# app-demo-recorder

Grabador de demos de la PWA para la landing y las redes. Lo usa un equipo en
Windows, Linux y Mac, desde VS Code, con Claude Code, Codex o Copilot. Estas
instrucciones valen para cualquier asistente.

## Grabar un demo

Cuando pidan un video o demo de una funcionalidad de la app ("grabá cómo se
configura una cancha", "hacé un demo de X"), seguí paso a paso
`.claude/skills/grabar-demo/SKILL.md`. Claude Code y Copilot lo cargan como
`/grabar-demo`; en otras herramientas, leelo y seguilo igual.

Cuando pidan arreglar un video ya grabado ("al video del alta le faltó cargar
desde un Excel", "no se ve…", "va muy rápido"), seguí
`.claude/skills/corregir-demo/SKILL.md` (`/corregir-demo`).

Referencia para escribir escenas: `docs/escribir-escenas.md`; la API está en
`recorder/demo.py`.

## Reglas

- Se ejecuta siempre con `uv run` (`uv run grabar.py …`, `uv run instalar.py`):
  nunca `.venv/bin/python` ni el python del sistema.
- Multiplataforma: rutas con `pathlib`, nada de `/tmp`, señales POSIX sin
  alternativa para Windows ni comandos que solo existan en bash. Todo
  `read_text`/`write_text`/`subprocess` de texto con `encoding="utf-8"`.
- `config.py` es compartido (va a git). Lo personal (credenciales, `APP_URL`,
  `APP_DIR`) va solo en `.env`: no lo leas, no lo muestres y nunca pongas
  credenciales en config.py, escenas ni logs. Lo que haga falta de `.env` lo
  muestra `uv run grabar.py --listar`.
- Las escenas usan siempre los métodos de `d.` (no `d.page.click` directo),
  salvo en `prepare()`, que corre fuera de cámara.
- Nada de IDs de la base en las escenas: las rutas usan los datos del login
  (`"/league/{liga}/…"`), porque staging y la base de cada uno tienen IDs distintos.
- Lo que se graba en una máquina es un borrador. Los videos finales salen del
  workflow `.github/workflows/escenas.yml` (ver `CONTRIBUTING.md`).
- Antes de dar un video por terminado, mirá sus cuadros:
  `uv run grabar.py <escena> --hoja` genera las hojas. Si no podés ver
  imágenes, pedile a la persona que las abra y te confirme.
- Los videos (`salida/`) no van a git.
- Independiente: la voz y el agrupado de subtítulos están adaptados de
  auto-video-generator en `recorder/voice.py` y `recorder/subtitles.py`; no
  dependas de otros proyectos.
