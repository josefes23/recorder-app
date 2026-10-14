# video-studio

Interfaz web local para el generador de Reels. Convierte en formulario el proceso
que antes se hacía a mano por terminal: guion → voz → escenas → render, con
previsualización antes de esperar los minutos del render completo.

Es de un solo usuario y se abre en `localhost`. No lleva login ni está pensada
para exponerse a internet.

## Arrancar

```bash
cd video-studio
./run.sh                 # http://127.0.0.1:8000
```

Compila la interfaz si hace falta y la sirve junto a la API en un solo proceso.

Para trabajar sobre la interfaz, con recarga en caliente:

```bash
./run.sh --dev           # interfaz :3000 · API :8000
```

Equivale a `cd web && npm run dev`, que levanta ambos procesos con la salida
etiquetada `[api]` y `[web]`. `Ctrl+C` los mata a los dos.

### Comandos desde `web/`

| Comando | Qué hace |
|---|---|
| `npm run dev` | API + Next con recarga en caliente |
| `npm run api` | Solo la API de Python (:8000) |
| `npm run dev:web` | Solo Next (:3000), útil si ya tienes la API levantada |
| `npm run export` | Compila la interfaz a `web/out` |
| `npm run serve` | Compila y sirve todo desde FastAPI |
| `npm run typecheck` / `npm run lint` | Comprobaciones |

## Depende de auto-video-generator

Este proyecto **no duplica el motor**: importa `auto-video-generator/scripts/generate.py`
como librería y no lo modifica. Ambas carpetas deben colgar del mismo directorio padre:

```
CreacionContenido/
├── auto-video-generator/   ← el motor (voz, subtítulos, render)
└── video-studio/           ← esta interfaz
```

Los ajustes de estilo se aplican sobrescribiendo las constantes del módulo en
tiempo de ejecución, que es como `generate.py` las lee — dentro de las funciones,
no en el import. Por eso la interfaz puede cambiar tamaño de letra o posición sin
tocar una línea del generador.

## Qué hace cada parte

| Paso | En la interfaz |
|---|---|
| Guion | Campo de tema → «Escribir con …» o «Plantilla» → **lo editas tú** antes de seguir. Contador de palabras y segundos, con aviso si te sales de 30–45 s. Panel plegable para elegir proveedor, clave y modelo |
| Voz | Doce voces en español con velocidad y tono |
| Subtítulos | Tamaño, borde, altura, texto por bloque y líneas máximas |
| Escenas | Añades fondos y marcas en qué segundo entra cada uno |
| Previsualización | Un fotograma con fondo y subtítulos aplicados, en segundos |
| Render | Cola con barra de progreso real (fotograma N de M) |
| Biblioteca | Reproductor, descarga, borrado y «Reutilizar» para clonar los ajustes |

## Guiones con IA (opcional)

Sin credenciales la app funciona igual: escribes el guion a mano o usas la
plantilla local. Para que lo redacte un modelo hace falta una clave.

Lo normal es ponerla desde la interfaz: en la tarjeta **1 · Guion**, despliega
«Modelo del guion» y ahí eliges proveedor, pegas la clave y seleccionas modelo
de un desplegable. Se guarda en `video-studio/.env` (con permisos `600`) y surte
efecto sin reiniciar el servidor. La clave nunca vuelve al navegador: la
interfaz solo recibe sus últimos cuatro caracteres para que sepas cuál hay.

El desplegable de NVIDIA se llena con el catálogo vivo de `build.nvidia.com`,
filtrado a modelos de chat y con unos cuantos recomendados arriba; el de
Anthropic se pide a su API cuando ya hay clave.

También se puede editar el `.env` a mano:

```
# NVIDIA NIM — gratis. Saca la clave en https://build.nvidia.com
NVIDIA_API_KEY=nvapi-...
NVIDIA_MODEL=meta/llama-3.3-70b-instruct   # opcional, otro del catálogo

# Google Gemini — nivel gratuito con límites. Clave en https://ai.google.dev
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-3.6-flash               # opcional, otro del catálogo

# DeepSeek — de pago por uso. Clave en https://platform.deepseek.com
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-v4-flash            # opcional; el otro es -pro

# Anthropic — de pago por uso
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-5               # opcional
```

Con varias claves puestas gana la primera de la lista; `SCRIPT_PROVIDER=deepseek`
fuerza otra (es lo que escribe el desplegable al guardar). Un proveedor sin clave
se ignora, así el botón «Escribir» nunca queda activo para fallar al pulsarlo. El
rótulo de la cabecera y el botón dicen en todo momento qué modelo va a escribir.

**Cuál elegir.** NVIDIA es gratis pero su nivel gratuito encola: medido, entre
noventa segundos y más de tres minutos por guion, y el tamaño del modelo apenas
influye —un 3B tardó lo mismo que un 70B—. Google tiene nivel gratuito con
límites de uso. DeepSeek y Anthropic se cobran por uso y contestan en segundos.
Como redactar es un trabajo encolado, la lentitud ya no rompe nada; solo se hace
esperar.

NVIDIA, Google y DeepSeek exponen el mismo endpoint compatible con OpenAI, así
que comparten implementación —en el caso de Google, su capa de compatibilidad en
lugar de la API nativa: un guion es un system y un user sin streaming, justo lo
que cubre—. Cada proveedor es una entrada de `PROVIDERS` en `scriptgen.py` con
dónde vive su clave, qué catálogo ofrece y cómo se le pide un guion. Añadir otro
es añadir una entrada, sin condicionales repartidos.

El presupuesto de tokens va holgado (4096) porque los modelos que razonan lo
gastan pensando antes de escribir: medido con Gemini 3.6 Flash, 980 tokens de
razonamiento y solo 40 para el guion, que salía cortado a mitad de frase. Con
holgura son 100 palabras en unos diez segundos. Aun así se comprueban dos cosas
antes de dar por bueno el resultado —que el modelo no haya cortado por longitud
y que el guion pase de cincuenta palabras—, porque un guion partido por la mitad
se colaba como válido.

Del catálogo de NVIDIA vale cualquier modelo **de chat**. Los de visión
(PaliGemma y demás) son imagen → texto y no sirven para redactar el guion: por
eso el desplegable los deja fuera.

## Fondos

La galería lee `auto-video-generator/assets/backgrounds/`. Desde el mismo diálogo
puedes buscar y descargar clips de Pexels (necesita `PEXELS_API_KEY` en el `.env`
del generador, que ya está configurado) o subir archivos propios.

## Decisiones de arquitectura

**Un render por vez, en un proceso aparte.** Un render tarda varios minutos y
satura la CPU; dentro del servidor bloquearía la interfaz. La cola es un hilo con
`queue.Queue` y `subprocess` — para un solo usuario, Redis o Celery serían
servicios que mantener sin ganar nada.

**Redactar es un trabajo encolado, no una petición que espera.** Medido contra
NVIDIA, un guion tarda entre cuarenta segundos y dos minutos. Sostener la
petición HTTP abierta mientras tanto era lo que reventaba en desarrollo: el
proxy de Next corta las reescrituras a los treinta segundos y el navegador veía
un `ECONNRESET`. Ahora `POST /api/script` publica el encargo y contesta en
milisegundos con la clave del trabajo; el guion llega por `GET /api/events`
cuando está listo.

**El log de eventos es la arquitectura de Kafka sin el broker.** `eventlog.py`
es un log append-only sobre la misma base SQLite, con las garantías que
importan: los eventos solo se añaden y nunca se reescriben, cada uno tiene un
`offset` monótono que es la posición del consumidor, la clave agrupa los
eventos de un mismo trabajo, la entrega es *al menos una vez* —se confirma el
offset después de trabajar, no antes— y por eso el consumidor comprueba si el
trabajo ya está resuelto antes de repetirlo. Los offsets de cada grupo se
guardan, así que un reinicio sigue donde estaba. Y antes de redactar, el
consumidor **reserva** el trabajo con una sentencia atómica de SQLite: puede
haber más de un backend contra la misma base —pasa sin querer al levantar
`./run.sh` y `npm run dev` a la vez— y sin eso los dos redactan el mismo guion.
La reserva caduca a los diez minutos para que un consumidor muerto no bloquee el
trabajo, que es lo que la entrega al menos una vez intenta evitar. No hay broker
de verdad a
propósito: esto es localhost para un solo usuario, y levantar Kafka para
redactar cien palabras sería mantenimiento a cambio de nada — la misma razón
por la que la cola de renders es un hilo y no Celery. Si algún día hace falta,
se reescriben `publish()` y `read_after()` y nadie más se entera.

**El front escucha por SSE, no pregunta.** Es un flujo de una sola dirección, y
`EventSource` reconecta solo y reenvía `Last-Event-ID`. Como cada evento lleva
su offset, el servidor reanuda en el punto exacto: un corte de la conexión deja
de perder eventos, que es justo lo que las posiciones compran. En el cliente,
`job-tracker.ts` convierte el flujo en promesas por trabajo con la convención
del log —`.completed` resuelve, `.failed` rechaza— así que añadir tipos de
trabajo nuevos no obliga a tocarlo.

**El estado compartido va bajo cerrojo, no bajo conexión por hilo.** FastAPI
ejecuta cada endpoint síncrono en un hilo distinto del pool, y el hilo de la
cola de renders escribe en la misma base. Con la conexión SQLite compartida sin
sincronizar, dos peticiones a la vez devolvían filas vacías o reventaban con
«bad parameter or other API misuse» — medido: siete fallos de cada ciento
veinte. Un `RLock` en `db.py` las serializa, que con un solo usuario no cuesta
nada y evita tener que mantener una conexión por hilo con sus bloqueos de
escritura. La previsualización lleva su propio cerrojo por el mismo motivo:
`apply_style` escribe en las constantes del generador, que son globales del
proceso, así que dos previsualizaciones simultáneas se pisaban el estilo. Y la
respuesta viaja como bytes en vez de como archivo, para que una petición no
pueda sobrescribir el PNG que otra está enviando.

**El progreso sale de moviepy.** `app/render_worker.py` reimplanta el ensamblado
final en lugar de llamar a `gen.render()`, porque esa función no acepta un
`logger` y sin él no habría barra de progreso. La lógica con sustancia
(`build_caption_clips`) se reutiliza tal cual.

**La interfaz es Next.js exportado, no un servidor de Next.** Todo el estado vive
en el cliente y la API es FastAPI, así que no hace falta ni renderizado en
servidor ni un segundo proceso en marcha. `output: 'export'` produce HTML y JS
estáticos que sirve el propio backend; el servidor de desarrollo solo se levanta
cuando estás editando la interfaz.

**Una sola hoja de estilos, con tokens y sin peleas de cascada.** `globals.css`
declara la escala de color, espacio y tipografía en `:root`, y ningún componente
escribe un color literal. Los estilos base van dentro de `:where()`, así que
pesan cero en especificidad y cualquier clase los sobrescribe sin `!important`.
El espacio lo reparte el contenedor con `gap`, nunca el margen del hijo: añadir
un control no descuadra a sus vecinos. Añadir un paso nuevo es componer `Step` y
`Field` de `web/shared/ui/`, sin tocar el CSS.

**La interfaz va por capas, y el linter las vigila.** Las dependencias apuntan
hacia dentro: `domain` son reglas puras —duración del guion, línea de tiempo de
escenas, formato de voz— sin React ni red; `application` orquesta esos casos de
uso contra el puerto `StudioGateway`; `infrastructure` implementa ese puerto por
HTTP; las features montan la interfaz. La implementación del gateway solo la
conoce `app/page.tsx`, que es la raíz de composición y se lo inyecta al
proveedor. Esa regla no es un acuerdo de palabra: `eslint.config.mjs` la aplica
con `no-restricted-imports`, así que importar `infrastructure` desde una feature
no compila el lint.

Lo que se gana en la práctica: el dominio se prueba con `npm test` en
milisegundos, sin navegador ni servidor ni datos falsos, y montar el estudio
contra un doble de pruebas es cambiar el argumento `gateway`.

**Cada feature guarda su propio estado.** `script`, `voice`, `captions`,
`scenes`, `backgrounds`, `render`, `library` y `writer` tienen su `model/` con
un slice y su `ui/` con los componentes. El proveedor los junta y resuelve solo
lo que ninguna feature puede resolver sola: previsualizar, renderizar y
reutilizar un video, que necesitan datos de varias a la vez. Los componentes ya
no reciben un objeto `studio` por props; piden su propio hook.

**Un panel para los cuatro pasos, no cuatro tarjetas.** Guion, voz, subtítulos y
escenas son una secuencia —la duración del guion condiciona a las escenas—, así
que van numerados dentro del mismo panel y separados por filetes. Lo que se
ajusta una vez y no se vuelve a mirar (el modelo del guion, el ajuste fino de
los subtítulos) vive en plegables, que es lo que mantiene la superficie
principal en unos pocos controles.

**Las escenas se dibujan en una línea de tiempo.** La barra reparte la duración
del vídeo entre las escenas, marca dónde acaba la voz y pinta en rojo las que
entran después. Cada fila dice su tramo —del segundo tal al tal— y cuántos
segundos estará en pantalla. Una lista de segundos de entrada no enseña ni los
huecos, ni las escenas muertas, ni cuánto dura realmente cada una; la barra sí.

**Y avisa de si el clip se va a repetir.** Cuando el fondo dura menos que su
tramo, `build_background` lo encadena consigo mismo hasta cubrirlo. La interfaz
lo anticipa con la **misma fórmula del motor**, así que el número que enseña es
el que va a ocurrir; copiar la cuenta a ojo habría sido peor que no decir nada.
Las imágenes quedan fuera del aviso: a esas el motor les aplica un zoom lento
que cubre el tramo entero, no las repite.

**La previsualización no renderiza vídeo.** Compone un solo fotograma con PIL:
segundos en lugar de minutos, que es lo que hace usable el ajuste de estilo.

## Estructura

```
video-studio/
├── app/
│   ├── engine.py          # puente al motor + previsualización
│   ├── render_worker.py   # render en subproceso, progreso por stdout
│   ├── jobs.py            # cola de renders, un trabajo a la vez
│   ├── eventlog.py        # log append-only con offsets y grupos
│   ├── scriptjobs.py      # consumidor: encargo de guion → guion redactado
│   ├── db.py              # historial en SQLite
│   ├── scriptgen.py       # guiones con NVIDIA NIM o Claude
│   └── main.py            # API FastAPI + flujo SSE de eventos
├── web/                   # interfaz Next.js (App Router + TypeScript)
│   ├── app/               # rutas y estilos · raíz de composición
│   ├── domain/            # reglas puras + sus pruebas (npm test)
│   ├── application/       # puerto StudioGateway y casos de uso
│   ├── infrastructure/    # el adaptador HTTP del puerto
│   ├── features/          # una carpeta por feature, con model/ y ui/
│   │   └── studio/        # el shell: proveedor, estado compartido, acciones
│   ├── shared/ui/         # Step, Field, Slider, Disclosure
│   └── out/               # build estático (generado, ignorado por git)
└── data/                  # SQLite, vídeos, miniaturas — todo ignorado por git
```

## Requisitos

- Python 3.9+ (probado en 3.13)
- Node.js 18+ (probado en 24) — solo para compilar la interfaz
- ffmpeg (`brew install ffmpeg`)
- Internet para la síntesis de voz
