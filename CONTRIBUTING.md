# Cómo trabajamos

## Qué va a git y qué no

| Va a git (compartido) | No va a git (personal o generado) |
|---|---|
| `escenas/*.py`: cada video es código | `.env`: tus credenciales y rutas |
| `config.py`: voz, música, subtítulos, login | `salida/`: los videos |
| `musica/`, `fonts/`: pistas y fuentes con licencia | `.cache/`, `.venv/` |
| `AGENTS.md`, `.claude/`, `.codex/`, `.vscode/`: el flujo `/grabar-demo` y los permisos de cada asistente | `.claude/settings.local.json` |

Los videos terminados se suben a la carpeta compartida del equipo:
**`<link a la carpeta compartida>`**, en una subcarpeta por escena.

## Flujo para un video nuevo

1. Actualizá `main` y creá una rama: `escena/<nombre>` (por ejemplo `escena/configurar_cancha`).
2. Pedile el demo a tu asistente (Claude Code o Copilot: `/grabar-demo <funcionalidad>`;
   Codex: "grabá un demo de <funcionalidad>"), o escribí la escena a mano
   ([docs/escribir-escenas.md](docs/escribir-escenas.md)).
   Para revisar los cuadros: `uv run grabar.py <escena> --hoja`.
3. Mirá los videos completos, con sonido y sin sonido, y pasá la
   [lista de revisión](#lista-de-revisión).
4. Abrí un PR con la escena (`escenas/<nombre>.py`). En la descripción poné el
   link a tu borrador en la carpeta compartida y la transcripción.
5. Otra persona del equipo revisa el video, no solo el código, y aprueba.
6. Merge, y después el video final: en GitHub, **Actions → Escenas contra
   staging → Run workflow**, modo `final` y el nombre de la escena. Bajá el
   artefacto del run y subí a la carpeta compartida los `.mp4`, los `.jpg`,
   los `.vtt` y el `.json`. Ese es el video que se publica.

Los finales salen siempre de ese workflow, no de la máquina de nadie: así
todos se ven igual y cada uno trae en su `.json` el commit que lo generó
([por qué](docs/adr/001-entorno-de-grabacion.md)). Lo que grabás en tu
máquina es un borrador para revisar.

Cuando cambia la app (nueva pantalla, otro texto en un botón), el mismo
workflow corre cada día hábil una prueba de todas las escenas y falla si
alguna se rompió. Arreglala en su propio PR y regrabá el final.

## Datos demo

Las escenas se graban contra **staging**, con una **cuenta demo** y una
**liga demo** que todos comparten.

- **La cuenta demo** es solo para esto: con los permisos mínimos para las
  escenas, solo en staging, nunca una cuenta personal ni de producción. Sus
  datos van en tu `.env` y en los secretos del repo (`DEMO_EMAIL`,
  `DEMO_PASSWORD`). Si alguien la expone, se cambia la contraseña y se avisa.
- **La liga demo** la arma un script de datos en el repo de la app, que se
  puede volver a correr para dejarla como nueva. Tiene que tener lo que
  piden las escenas (cada una lo anota en su docstring, en "Necesita"):

  | Escena | Necesita |
  |---|---|
  | `configurar_cancha` | Un complejo con horario semanal y sin una cancha "Cancha Techada" |

  Si una escena nueva necesita otra cosa, sumala a esta tabla y al script en
  el mismo PR.
- **Sin IDs en las escenas.** Cada entorno tiene los suyos: las rutas usan
  `{liga}`, que sale del login ([escribir escenas](docs/escribir-escenas.md#datos-y-rutas)).
- **Grabar contra tu base local** sirve para escribir y probar escenas si
  tenés los mismos datos, pero los finales salen de staging.

## Lista de revisión

- [ ] Se entiende qué resuelve la funcionalidad en la primera frase.
- [ ] Cada acción ocurre mientras se la narra, no antes ni después.
- [ ] No hay pantallas de carga, errores ni avisos que no vienen al caso.
- [ ] Datos prolijos y creíbles: nombres reales, nada de "test123".
- [ ] No aparecen emails, teléfonos ni datos de personas reales. El grabador
      blurea solo emails, teléfonos, documentos y los datos de la cuenta;
      lo demás (nombres de jugadores, por ejemplo) se agrega en `OFUSCAR`.
- [ ] Los subtítulos se leen bien y no tapan nada importante.
- [ ] Dura entre 15 y 40 segundos.
- [ ] Se ve bien en celular **y** en escritorio.

## Reglas del equipo

- **Una escena = una funcionalidad = un video.** Nombre en `snake_case`: es el
  nombre del archivo de video.
- **Cuenta demo compartida** (ver [Datos demo](#datos-demo)). Todos grabamos con la misma, así que:
  - cada escena deja los datos como los encontró (`prepare()` borra lo de la toma anterior);
  - no graben dos personas la misma escena a la vez: una borraría lo de la otra.
    El workflow ya lo respeta: corre una grabación por vez.
- **`config.py` afecta a todos.** Cambiar voz, música, velocidad o estilo de
  subtítulos cambia todos los videos: hacelo en un PR aparte y avisá al equipo.
- **Música solo con licencia comercial.** Anotá origen y licencia de cada pista
  en [musica/LEEME.md](musica/LEEME.md) en el mismo PR que la agrega.
- **Nada de credenciales en el código**: van solo en `.env` y en los secretos
  del repo. Los asistentes tienen bloqueado leer `.env` (`.claude/`,
  `.codex/`, `.vscode/`), pero es una barrera blanda: lo que protege de
  verdad es que la cuenta demo tenga permisos mínimos.
- **Voz de los finales**: el workflow usa Azure AI Speech si el repo tiene
  `AZURE_SPEECH_KEY`. edge-tts, la voz por defecto, no es un servicio
  oficial: sirve para borradores.

## Guion

- Español rioplatense con la voz `es-AR-*` (tocá, escribí, tenés).
- Frases cortas y habladas, de 8 a 15 palabras. Una idea por frase.
- Beneficio antes que mecánica: "tus jugadores ven el fixture al instante" antes que "tocá publicar".
- Cifras en letras ("treinta por ciento"): la voz las lee mejor.
- Estructura: qué resuelve (1 frase) → pasos (2 a 4 frases) → resultado.
