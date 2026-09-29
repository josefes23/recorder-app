# Cómo trabajamos

## Qué va a git y qué no

| Va a git (compartido) | No va a git (personal o generado) |
|---|---|
| `escenas/*.py`: cada video es código | `.env`: tus credenciales y rutas |
| `config.py`: voz, música, subtítulos, login | `salida/`: los videos |
| `musica/`: pistas con licencia | `.cache/`, `.venv/` |
| `.claude/`: la skill `/grabar-demo` y los permisos | `.claude/settings.local.json` |

Los videos terminados se suben a la carpeta compartida del equipo:
**`<link a la carpeta compartida>`**, en una subcarpeta por escena.

## Flujo para un video nuevo

1. Actualizá `main` y creá una rama: `escena/<nombre>` (por ejemplo `escena/configurar_cancha`).
2. En Claude Code: `/grabar-demo <funcionalidad>`, o escribí la escena a mano
   ([docs/escribir-escenas.md](docs/escribir-escenas.md)).
3. Mirá los videos completos, con sonido y sin sonido, y pasá la
   [lista de revisión](#lista-de-revisión).
4. Abrí un PR con la escena (`escenas/<nombre>.py`). En la descripción poné el
   link a los videos en la carpeta compartida y la transcripción.
5. Otra persona del equipo revisa el video, no solo el código, y aprueba.
6. Merge: el video de la carpeta compartida queda como versión final.

Cuando cambia la app (nueva pantalla, otro texto en un botón), regrabá todo
con `uv run grabar.py`. Si una escena falla, arreglala en su propio PR.

## Lista de revisión

- [ ] Se entiende qué resuelve la funcionalidad en la primera frase.
- [ ] Cada acción ocurre mientras se la narra, no antes ni después.
- [ ] No hay pantallas de carga, errores ni avisos que no vienen al caso.
- [ ] Datos prolijos y creíbles: nombres reales, nada de "test123".
- [ ] No aparecen emails, teléfonos ni datos de personas reales.
- [ ] Los subtítulos se leen bien y no tapan nada importante.
- [ ] Dura entre 15 y 40 segundos.
- [ ] Se ve bien en celular **y** en escritorio.

## Reglas del equipo

- **Una escena = una funcionalidad = un video.** Nombre en `snake_case`: es el
  nombre del archivo de video.
- **Cuenta demo compartida.** Todos grabamos con la misma, así que:
  - cada escena deja los datos como los encontró (`prepare()` borra lo de la toma anterior);
  - no graben dos personas la misma escena a la vez: una borraría lo de la otra.
- **`config.py` afecta a todos.** Cambiar voz, música, velocidad o estilo de
  subtítulos cambia todos los videos: hacelo en un PR aparte y avisá al equipo.
- **Música solo con licencia comercial.** Anotá origen y licencia de cada pista
  en [musica/LEEME.md](musica/LEEME.md) en el mismo PR que la agrega.
- **Nada de credenciales en el código**: van solo en `.env`.

## Guion

- Español rioplatense con la voz `es-AR-*` (tocá, escribí, tenés).
- Frases cortas y habladas, de 8 a 15 palabras. Una idea por frase.
- Beneficio antes que mecánica: "tus jugadores ven el fixture al instante" antes que "tocá publicar".
- Cifras en letras ("treinta por ciento"): la voz las lee mejor.
- Estructura: qué resuelve (1 frase) → pasos (2 a 4 frases) → resultado.
