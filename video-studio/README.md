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

En Windows, `run.sh` no corre (es bash): usa `py run.py`, que hace lo mismo.
`run.sh` solo llama a `run.py`, así que las dos formas arrancan igual.

Compila la interfaz si hace falta y la sirve junto a la API en un solo proceso.

Para trabajar sobre la interfaz, con recarga en caliente:

```bash
./run.sh --dev           # interfaz :3000 · API :8000  (Windows: py run.py --dev)
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
| Escenas | Un guion visual (estilo, personajes y qué se ve en cada tramo) y una imagen generada por tramo, o el fondo que elijas de Pexels o la galería; marcas en qué segundo entra cada uno |
| Descripción | El texto para publicar: palabras clave al principio, resumen y hashtags. «Escribir con IA» o a mano, hasta 5000 caracteres, con aviso de dónde cortan Instagram y TikTok |
| Previsualización | Tres pestañas: la **portada** (título gancho sobre una imagen, se repinta sola al cambiarla), un fotograma con fondo y subtítulos, y la **animática** (las escenas con su ritmo y sus transiciones, antes de renderizar) |
| Render | Cola con barra de progreso real (fotograma N de M); al terminar, «Descargar video», «Descargar portada» y «Copiar descripción» |
| Biblioteca | Cuadrícula de portadas con búsqueda (tema, guion o descripción), filtros por estado y formato y de doce en doce; reproductor con sonido que pasa de un video a otro, descarga del video y de su portada, copia de su descripción, borrado con confirmación en la tarjeta y «Reutilizar» para clonar los ajustes (portada y descripción incluidas) |

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
que cubre—. Cada proveedor es una entrada de `PROVIDERS` en `app/domain/writer.py`
(dónde vive su clave, modelo por defecto) y un `Endpoint` en
`app/infrastructure/llm/composer.py` (cómo se le habla). Añadir otro es añadir
esas dos entradas, sin condicionales repartidos.

El presupuesto de tokens va holgado porque los modelos que razonan lo gastan
pensando antes de escribir: medido con Gemini 3.6 Flash, 980 tokens de
razonamiento y solo 40 para el guion, que salía cortado a mitad de frase. Con
holgura son 100 palabras en unos diez segundos. Lo fija cada proveedor
(`Provider.max_tokens`): 8192 en Google, DeepSeek y Anthropic, para que quepa
el guion visual de un cortometraje (hasta 30 escenas con descripción y
movimiento), y 4096 en NVIDIA, que no publica su límite por modelo. Es un
techo, no un gasto: un guion corto cuesta lo mismo con uno que con otro. Aun así se comprueban dos cosas
antes de dar por bueno el resultado —que el modelo no haya cortado por longitud
y que el guion pase de cincuenta palabras—, porque un guion partido por la mitad
se colaba como válido.

Del catálogo de NVIDIA vale cualquier modelo **de chat**. Los de visión
(PaliGemma y demás) son imagen → texto y no sirven para redactar el guion: por
eso el desplegable los deja fuera.

## Fondos

La galería lee `auto-video-generator/assets/backgrounds/`. Desde el mismo diálogo
puedes buscar en Pexels: la búsqueda enseña miniaturas de los clips verticales
sin descargar nada, «Ver» abre cualquiera a tamaño grande y en movimiento (la
versión ligera de Pexels), marcas los que quieres y solo se bajan esos, con el
mismo nombre que les daría el script del generador («finanzas_6799744.mp4»),
así que la galería los agrupa por búsqueda. Los que ya están en la galería
aparecen señalados. Necesita `PEXELS_API_KEY` en el `.env` del generador (que ya está
configurado). También puedes subir archivos propios. En tu galería, «Ver» abre
cualquier fondo a tamaño grande (los vídeos se reproducen) y «×» lo borra,
archivo y miniatura incluidos; si alguna escena lo usaba, desaparece de la
línea de tiempo. Cada escena tiene también su «Ver».

## Escenas con imágenes generadas (opcional)

«Generar escenas desde el guion» trocea el guion por sentido: el modelo del
guion recibe las frases numeradas, con lo que tarda cada una, y decide en qué
frase cambia la imagen —otra persona, otro lugar, otra idea, un «segundo» o
«tercero»—, en escenas de 3 a 9 segundos y como mucho ocho. Antes se troceaba
solo por longitud (tramos de unos seis segundos) y una imagen podía juntar el
final de una idea con el principio de la siguiente: Josefo seguía en pantalla
mientras la voz decía «Segundo, el bautismo y la crucifixión». Nunca se parte
una frase. Si el modelo devuelve más de ocho escenas, se quedan las que caen al
principio de cada tramo del reparto por longitud, con sus descripciones. Cada
escena entra en el segundo en que empieza su texto, estimado al mismo ritmo
que la duración del guion.

Ese segundo es solo una estimación (2,7 palabras/s) y la voz real no va a
ritmo fijo: las palabras largas, los números y la pausa de cada punto la
alargan, y el error se acumula. En un guion de palabras largas la voz duró 58 s
frente a 51,5 estimados, y desde la tercera escena cada imagen entraba de 4 a
7 s antes que su texto. Por eso, al renderizar, cada escena —del guion visual o
puesta a mano— se traduce a la palabra del guion donde cae y entra cuando la voz
la dice, en mitad de la pausa que la precede (`domain.scene.synced_to_voice`,
con las marcas por palabra de edge-tts). La línea de tiempo del estudio sigue
enseñando los segundos estimados.

Antes de pintar, el modelo del guion (el de «Modelo del guion») escribe un
**guion visual**: un estilo común, lo que se repite —personas, animales,
objetos como una máquina de dibujos o un juego, lugares— con sus rasgos fijos
(edad, cara, pelo y ropa; o forma, materiales y colores) y lo que se ve en cada
escena, contado como un plano de película. El generador pinta cada imagen por
separado y sin ver las demás, así que cada encargo lleva su escena, los rasgos
de los elementos que nombra, el estilo y la misma semilla para todo el video.
Sin eso, cada imagen se inventaba un protagonista distinto y, como recibía la
frase de la voz, la escribía encima. Estilo y elementos se pueden retocar en el
panel; al pedir otra imagen para una escena, nombrar a uno basta para que salga
igual. Como mucho seis elementos por video.

Dos detalles probados contra FLUX.2: no admite instrucciones negativas («sin
texto» no quita letras, y lo que va entre comillas lo escribe), y llamar a la
imagen «fotograma de película» evita que pinte rótulos, que en temas religiosos
salían como versículos. El filtro de contenido de Cloudflare bloquea algunas
escenas (cuerpos mojados, por ejemplo en un bautismo); esa escena se marca con
el motivo y se puede pedir otra vez con otra descripción.

### Revisión de cada imagen

Si el modelo del guion ve imágenes (Claude o Gemini), revisa cada una antes de
darla por buena, con la descripción que se pidió delante. La rechaza solo por
fallos que se notan en el móvil: manos, brazos o dedos de más, cuerpos fundidos
o superpuestos, letras inventadas o escritas encima, o una escena que no tiene
nada que ver. Si ve un fallo, se repinta con otra semilla (la misma repetiría la
imagen), hasta tres imágenes por escena; entra la primera aprobada o, si
ninguna lo está, la de menos fallos. A la galería solo llega la que se queda, y
debajo de la escena se cuenta qué pasó: «Revisada por Claude», qué se descartó
y por qué, o qué fallos quedan. Una revisión que falla —sin saldo, límite de
peticiones— no tumba la imagen: entra marcada como «sin revisar». Se desactiva
con la casilla del panel.

Medido con 21 imágenes de la galería —4 con fallos de anatomía (tres manos,
una mano suelta, cuerpos fundidos, un brazo de más), 3 más con letras
inventadas encima, 3 con rótulos dudosos y 11 limpias— y el mismo encargo de
revisión que usa el estudio:

| Revisor | Fallos cazados | Falsas alarmas | Anatomía |
|---|---|---|---|
| Claude Sonnet 5.5 | 6 de 7 | 0 de 11 | Ve 3 de 4: se le escapó una mano ambigua que entra por el borde |
| Claude Haiku 5.5 | 5 de 7 | 0 de 11 | Ninguna: solo rechaza por las letras |
| Llama 4 Scout (Cloudflare, gratis) | 5 de 7 | 0 de 11 | Ninguna: solo rechaza por las letras |
| Gemini 3.6 Flash (nivel gratuito) | — | — | Error 429 a la octava imagen |

Por eso revisa el modelo del guion y no uno barato aparte: lo que más se nota,
las manos y los cuerpos, solo lo ve el modelo grande.

Cada revisión con Sonnet 5.5 cuesta unos 0,006 $ (unos 2.500 tokens de entrada
por la imagen y el encargo, y unos 200 de salida) y tarda de 2 a 15 segundos. Con
Gemini en el nivel gratuito el límite de peticiones se agota enseguida; esas
imágenes quedan «sin revisar». Dos lecciones del ajuste: si el encargo pide que
la imagen cumpla la descripción, el revisor rechaza por cualquier detalle (un
gesto, un objeto) y casi todas las escenas gastan sus tres intentos; y a veces
contesta, se lo repiensa por escrito y vuelve a contestar, así que vale el
último veredicto. Las reglas viven en `app/domain/review.py`.

Los intentos tienen tope de tiempo además de número: no se empieza otro si el
encargo lleva más de tres minutos, porque la interfaz se da por vencida a los
cinco contando la cola.

### Corregir una imagen

Cada escena con imagen (no con clip) tiene el botón **Corregir**, y la vista
grande, «Corregir esta imagen». Se escribe qué está mal —«la mujer de la
izquierda tiene seis dedos», «quita las letras del cielo»— y la IA no pinta
otra: la imagen va al generador como primera referencia, con lo que hay que
arreglar y la orden de dejar lo demás como está. Si el revisor había visto
fallos, el cuadro se abre ya con ellos escritos.

Es el mismo encargo que una imagen nueva (`POST /api/illustrations` con
`source` y `correction`), así que pasa por la misma revisión: el revisor
recibe además qué se pidió arreglar y, si sigue a la vista, se repinta con
otra semilla partiendo otra vez de la original. La corregida entra en la
escena con nombre propio; la original sigue en la galería para volver atrás.

Las referencias de la biblioteca que salgan en la escena van detrás de la
imagen, así que caben tres en vez de cuatro. Con Cloudflare la imagen viaja
reducida a 768 px de lado mayor, como cualquier referencia (cuesta neuronas
por tesela); con Nano Banana, a 1536. Las referencias a Nano Banana no están
probadas contra la API: sin facturación no hay cupo de imagen.

### Biblioteca de personajes y elementos

Lo que se repite de un video a otro —la misma presentadora, una mascota, la
máquina de dibujos del canal— se guarda en una biblioteca. Cada elemento del
panel tiene su botón «Guardar»: queda guardado con su nombre, su tipo y sus
rasgos, y se le pinta una **imagen de referencia** con el estilo del video
abierto (un retrato de la cintura para arriba si es una persona, una foto de
producto si es un objeto, un plano general si es un lugar). Esa imagen pasa
por la misma revisión que las escenas, porque una referencia con una mano de
más estropearía todas las escenas donde sale. Guardar otra vez el mismo nombre
pone al día sus rasgos y repinta la referencia solo si cambiaron.

Por qué hace falta la imagen: los rasgos escritos mantienen la ropa y la forma,
pero la cara cambia en cada imagen. Probado con FLUX.2 [klein]: con un retrato
como referencia, la túnica y el manto salieron idénticos y la cara muy
parecida; sin él, otra ropa y otra cara.

Cómo se reutiliza:

- A mano, siempre: desde la biblioteca (desplegable bajo el reparto), «Usar en
  este video» lo mete en el reparto. Nada lo trae solo: el guion visual no ve
  la biblioteca, y lo que el modelo invente con el mismo nombre que algo
  guardado es un elemento nuevo, sin su referencia.
- Por qué: con la biblioteca ofrecida al guion visual, el modelo metía a los
  mismos en todos los videos —para él, una «Mujer moderna» guardada encaja en
  casi cualquier guion— y quitarlos del reparto no servía, porque volvían desde
  la biblioteca.
- El guion visual recibe lo que ya está en el reparto y se queda con lo que
  encaje: con su nombre, sus rasgos y su referencia de siempre, aunque el
  modelo los reescriba. Lo de otro tema lo deja fuera, así que un video sobre
  Kafka no arrastra al Jesús del anterior.
- En cada escena que nombra a un elemento guardado, su imagen de referencia va
  a FLUX (`input_image_0` a `input_image_3`, hasta cuatro por escena) y el
  encargo dice cuál es de quién con ordinales («Ana se ve igual que en la
  primera imagen de referencia; Pincel, que en la segunda»): la documentación de
  klein no aclara si la primera es la «imagen 0» o la «imagen 1».
- Al editar una escena se proponen, con un clic, los elementos del reparto que
  aún no nombra y los guardados que aún no están en el video.
- Desde la biblioteca también se repinta su referencia o se borra.

Solo Cloudflare manda referencias; con Nano Banana sin probar (sin facturación
no hay cupo), las escenas van solo con los rasgos. La imagen de referencia se
pinta una vez (unas 130 neuronas a 864x1536) y en cada escena viaja reducida a
432x768, unas 11 neuronas. Viven en `data/references/` (fuera de git) y la
biblioteca en la tabla `characters` de `data/studio.db`.

Pendiente de probar con imágenes reales: dos referencias en la misma escena.
Con una sola está probado; el día que se construyó se acabó el cupo de
Cloudflare antes de probar dos.

En el inspector de cada escena eliges: «⋯ → Cambiar por Pexels o la galería»
abre la galería y Pexels, y «Generar con IA» pide otra imagen con la
descripción que escribas. «Añadir con IA» crea una escena nueva desde una
descripción. Lo generado se guarda en la galería como un
fondo más, con nombre `ia-<tema>_<n>.jpg`, así que se puede reutilizar o borrar
como cualquier otro.

### Movimiento de las imágenes

Una imagen fija seis segundos se nota quieta, y el zoom del motor (un 7 %
repartido en toda la escena) casi no se veía. Al renderizar, el estudio parte
cada escena con imagen en planos de 3 a 4 segundos sobre la misma imagen, como
haría un montador con una foto: dentro de cada plano, un acercamiento lento y
constante (2 % por segundo); entre uno y otro, un corte a otro encuadre. El
primero es abierto; después se alternan uno cerrado sobre el motivo y uno
intermedio, cada vez ligeramente a un lado. El salto de escala, más del 10 %,
se lee como un corte buscado. Los encuadres cerrados miran a la mitad superior,
donde el guion visual pone las caras, lejos de los subtítulos. Una escena de 6
s da dos planos; una de 8, dos de 4; una de menos de 5, uno solo.

Lo hace el estudio y no el motor, que no se toca: el worker de render ya arma
la pista escena a escena y solo pide al motor cada fondo. Para las imágenes lo
pinta él (`app/domain/motion.py` decide dónde está la cámara en cada instante;
`app/infrastructure/motion.py` pinta los fotogramas). Cada fotograma recorta la
imagen con decimales y la escala en un solo paso (`Image.resize(box=…)`): el
zoom de moviepy redondea a píxeles enteros y en un zoom lento eso tiembla. Medido
fotograma a fotograma sobre una escena de 6 s, el cambio dentro de un plano se
mantiene parejo (de 1 a 2,5 de diferencia media por fotograma) y salta a 54
justo en el corte. Y sale más barato que antes: la pista de fondo pasó de 171 a
53 ms por fotograma, porque estas escenas ya salen a la medida del cuadro y se
ahorran el `CompositeVideoClip` que solo igualaba tamaños. Los clips de video
van como siempre: ya se mueven solos.

### Transiciones

En el paso de escenas, «Transición del video» elige cómo entran todas:
corte, fundido encadenado, fundido a negro, deslizar (la nueva empuja a la
anterior desde la derecha) o zoom de entrada, de 0,2 a 1,5 s. Cada escena puede
cambiarla en el inspector («Transición de entrada»), o pulsando su marca en la
línea de tiempo: ◆ si tiene una propia, ◇ si usa la del video. «Como el video»
vuelve a la común. Para varias a la vez, se marcan en la lista y «Aplicar
transición». Una escena con imagen fija usa la misma para sus cambios de
encuadre, así que con un fundido la foto pasa de un plano a otro disolviéndose
en vez de saltar. En la primera escena, que no entra desde ninguna, el selector
se llama «Cambios de encuadre» y solo sale si es una imagen. Por defecto es el
corte, y un video todo con cortes sale igual que antes.

Junto a cada selector, una vista previa mezcla las dos imágenes en el navegador
con la misma cuenta que el render (`look` en `web/domain/transition.ts`, copia
de la de Python), así que lo que se ve es lo que va a salir.

La transición se centra en el corte: empieza media transición antes y acaba
media después, así que la imagen nueva sigue entrando cuando la voz dice su
frase. Nunca dura más que ninguna de las dos escenas que une, para que dos
seguidas no se pisen. La común viaja con la producción y se guarda en el estilo
del video, y la de cada escena con la escena: «Reutilizar» recupera las dos.

`app/domain/transition.py` decide cuándo empieza y acaba cada cambio y cómo se
ve cada plano en cada instante; `app/infrastructure/transitions.py` mezcla los
fotogramas y encadena la pista. Fuera de los cambios cada fotograma es el del
plano que toca, tal cual: solo se pinta doble durante la transición.

### Qué dice la voz en cada escena

Para elegir la imagen que encaja hay que saber qué se cuenta mientras se ve. El
render no corta las escenas por segundos: cada una entra justo cuando la voz
dice una palabra concreta, la que cae en su segundo estimado a 2,7 palabras por
segundo (`synced_to_voice`). Así que qué palabras cubre cada imagen se sabe
antes de renderizar, y es exacto; lo que cambia al renderizar son los segundos.

- **La lista** dice en cada escena lo que se oye mientras se ve, y **el
  inspector** lo enseña entero con «Empieza con «palabra» ‹ ›» para adelantar o
  retrasar la entrada de palabra en palabra, sin pisar a las vecinas.
- **«Guion por escenas»**, la otra pestaña de la lista, parte el guion en
  trozos con la imagen de cada uno al lado. Con una escena elegida, tocar una
  palabra la hace entrar justo ahí.
- **Mover e intercambiar imágenes.** Si una imagen encaja mejor con otra frase,
  se lleva allí: arrastrando una fila de la lista y soltándola arriba o abajo
  de otra (se inserta y las de en medio se corren) o en su centro (se
  intercambian), arrastrando un tramo de la barra sobre otro (se
  intercambian), o sin arrastrar, con «‹ Antes», «Después ›» e «Intercambiar
  con…» del inspector, o Alt+↑ / Alt+↓ sobre la fila. Se mueve la imagen con
  todo lo suyo (lo que muestra, su movimiento, su clip, lo que se espera); el
  segundo y la transición se quedan en su sitio, así que la imagen pasa a
  acompañar lo que se dice ahí (`swapImages` y `moveImage`). Cada cambio deja un
  «Deshacer», que aplica el cambio contrario en vez de volver a una copia del
  estado anterior: una imagen que llegue entretanto no se pierde.
- **La animática con voz.** «Escuchar con la voz» genera solo la voz (edge-tts:
  gratis, unos segundos) y la animática suena con ella: la imagen, la frase y
  el segundo son los del render, porque el render usa esa misma toma. Si
  después cambia el guion o la voz, avisa de que la toma ya no vale.
- **Los tiempos reales de un video hecho.** Cada render guarda en su
  producción la clave de su toma; «Reutilizar» la recupera y el estudio enseña
  en qué segundo entró cada imagen de verdad, para ajustar y volver a
  renderizar.

Una toma (`app/domain/voice_take.py`) la identifica lo que se sintetiza: el
texto limpio, la voz, la velocidad, el tono y las voces del diálogo. La misma
entrada da la misma clave, así que el servidor (`POST /api/takes`) y el worker
de render la calculan igual y el render no vuelve a sintetizar lo que ya se
escuchó («Voz ya generada»). Se guardan en `data/takes/`: las marcas de cada
palabra siempre (pesan poco) y el audio de las últimas 40 (un mega por minuto).
La cuenta que reparte las palabras y pasa a segundos reales está copiada en
`web/domain/narration.ts`, con las mismas pruebas que la de Python.

Hay dos generadores, configurables en «Generador de imágenes» al final del paso
de escenas (o en `video-studio/.env`):

```
# Cloudflare Workers AI — gratis, 10.000 neuronas al día (se renuevan a las 00:00 UTC)
CLOUDFLARE_ACCOUNT_ID=...
CLOUDFLARE_API_TOKEN=...          # token con permiso de Workers AI
CLOUDFLARE_IMAGE_MODEL=@cf/black-forest-labs/flux-2-klein-4b   # opcional; o -9b

# Google Nano Banana — de pago: los modelos de imagen tienen cupo cero en el nivel gratuito
GEMINI_API_KEY=AIza...            # la misma que el guion con Gemini
GEMINI_IMAGE_MODEL=gemini-nano-banana-2.1   # opcional; -lite o gemini-3-pro-image

IMAGE_PROVIDER=cloudflare          # el que escribe el panel al guardar
```

FLUX.2 klein 4B a 864x1536 sale por unas 75 imágenes diarias dentro del cupo
gratuito, según la tabla de precios de Cloudflare; el 9B da más detalle pero
solo unas 7. Nano Banana 2.1 cuesta unos 0,05 $ por imagen a 2K. Las cifras son
orientativas: manda la página de precios de cada proveedor.

Cada generador es una entrada de `IMAGE_PROVIDERS` en `app/domain/illustration.py`
(qué datos pide, qué modelos ofrece) y un módulo en `app/infrastructure/imaging/`
(cómo se le habla). Nano Banana va por `generateContent`, la API nativa que
esos modelos anuncian en su catálogo; la guía de AI Studio documenta también la
API de Interactions, pero no enseña su respuesta y con una clave del nivel
gratuito no se puede comprobar.

### Escenas animadas (opcional, de pago)

Cualquier escena con imagen se puede convertir en un clip de video: **Gemini
Omni Flash** toma la imagen como primer fotograma e inventa el movimiento. El
clip entra en la galería al lado de su imagen (`<imagen>-mov-<id>.mp4`) y el
render lo usa como cualquier clip de Pexels: sin su audio y escalado a
1080x1920.

- **«Animar»** en el inspector de cada escena pide un clip del largo de su
  tramo, redondeado hacia arriba (de 3 a 15 s: lo que admite el modelo; un
  tramo más largo repite el clip). **«Reanimar»** pide otro desde la imagen
  original, y **«Volver a la imagen fija»** vuelve a ella; los clips anteriores
  se quedan en la galería. Marcando varias en la lista, **«Animar»** las pide
  todas y enseña el precio total antes de confirmar.
- **El interruptor «Animar cada imagen nueva»** (apagado de serie) anima sola
  cada imagen que llega a una escena. **«Animar las N escenas con imagen»**
  anima de una vez las que todavía no tienen clip.
- **«Movimiento al animar»**, en el inspector: qué se mueve y qué hace la cámara
  («el vapor sube; la cámara se acerca despacio»). Lo propone el guion visual
  —una frase por escena, que quepa en un solo plano sobre esa imagen— y se
  cambia a mano antes de animar o reanimar. Vacío, el clip lleva un movimiento
  sutil con la cámara lenta. Solo aparece con la animación configurada.
- Cada botón enseña el precio orientativo: unos 0,07 US$ por segundo a 720p
  (precio de Google del 16-11-2026). Un reel de 45 s animado entero ronda los
  3 US$.

Usa la misma clave que Nano Banana, con la facturación activada: Omni no tiene
nivel gratuito.

```
GEMINI_API_KEY=AIza...                      # la misma de las imágenes, con facturación
GEMINI_VIDEO_MODEL=gemini-omni-1.2-flash    # opcional
```

Un clip tarda minutos y el servidor anima dos a la vez, así que cada escena
espera el suyo sin bloquear nada; si renderizas antes, sale con su imagen fija.
Va por la API de Interactions (`app/infrastructure/animation/gemini_omni.py`):
pide el clip con entrega por URI, espera a que el archivo esté listo y lo baja.
Está probado contra la documentación y con un animador de mentira, pero no
contra la API real: no había una clave con facturación a mano.

## Cortometrajes: formato, duración, diálogos y música

En el paso 1 se elige el **formato** y la **duración**; el resto del estudio
se acomoda solo.

| | Reel | Cortometraje |
|---|---|---|
| Guion | 85–120 palabras (30–45 s) | 330–780 palabras (2–5 min), con planteamiento, nudo y desenlace |
| Escenas del guion visual | hasta 8 | hasta 30 |

| | Vertical 9:16 | Horizontal 16:9 |
|---|---|---|
| Video | 1080x1920 | 1920x1080 |
| Subtítulos | banda central baja | abajo, en menos líneas (se ajustan al cambiar de formato) |
| Imágenes, clips animados y Pexels | verticales | horizontales |
| Portada | 1080x1920 | 1280x720, la miniatura de YouTube |

**Duración a medida.** Además de Reel y Cortometraje, la duración puede ser
«Personalizada…»: se escribe una cantidad en segundos o minutos (de 20 s a
10 min). Viaja como `90s`, `300s`… por el mismo campo `length`; el redactor
recibe ese objetivo con un ±15 % de holgura y el tope de escenas se ajusta
(hasta 60 s se escribe como un reel, más largo como un corto).

Una imagen vertical que se usa en un video horizontal se encuadra más arriba,
donde las imágenes generadas ponen las caras.

**Diálogos.** Con «Guion con diálogos», el modelo escribe una intervención por
línea con el nombre en mayúsculas («ANA: ¿Viste eso?») y lo narrado con
«NARRADOR:». En el paso 2 aparece cada personaje con su voz: se asigna sola
—distinta de la del narrador y, a ojo, según el nombre (los terminados en «a»,
voz de mujer)— y se cambia a mano. Al renderizar, cada intervención se
sintetiza con su voz y se unen con una pausa corta; las etiquetas no se oyen
ni salen en los subtítulos. Sin el modo diálogo, el guion se lee entero con
una voz, como siempre: un «OJO: …» no pierde su primera palabra
(`app/domain/dialogue.py`).

**Música y sonido** (paso 3). La música sale de una galería propia
(`data/music/`, fuera de git): se suben pistas libres de derechos y se elige
una por video. Se repite hasta cubrir el video, entra y sale con un fundido y
baja sola mientras alguien habla (a un 35 % de su volumen, con rampas de 0,3 s;
`app/domain/music.py`). Aparte, se puede mezclar debajo de la voz el sonido
propio de los clips: los animados con Omni traen sonido ambiente.

Todo esto viaja en cada encargo (guion, guion visual, imagen, animación,
vista previa, portada y render) y se guarda con el video dentro de su `style`,
bajo la clave `production`: así «Reutilizar» lo recupera y la base no cambia de
esquema (un servidor de una versión anterior la sigue leyendo).

## Prompts

El botón **Prompts** de la barra superior abre todos los prompts que el estudio
manda por debajo (guion, guion visual, imágenes, animación, portada,
descripción y los consejos de Optimizar). Cada uno es una plantilla: el texto
se edita y las `{variables}` las rellena el programa con los datos del video.
Debajo se ve el prompt ya montado con datos de ejemplo. Lo editado se guarda
en la tabla `prompt_overrides` de `studio.db` y vale para los videos nuevos;
«Restaurar» vuelve al original. El tema y las frases numeradas viajan aparte
como mensaje del usuario y no se editan.

## Optimizar: ganchos, retención y puntaje

El paso 6 reúne lo que haría un vidIQ, con el modelo del guion y sobre el
video abierto: **ganchos** para los tres primeros segundos, **retención**
(dónde se cae el guion y cómo arreglarlo), **títulos** con nota, **SEO** de la
descripción (puntaje, versión mejorada y etiquetas), **puntaje** del video
entero y **tendencias e ideas** de videos nuevos. Hay atajos: «Ganchos» junto
al guion y «Puntuar SEO» junto a la descripción. Un gancho puede ponerse como
primera frase del guion (el siguiente lo sustituye, no se apilan).

Ojo: el modelo **no consulta datos en vivo** de YouTube, TikTok ni Instagram.
Los puntajes y las «tendencias» son criterio, no estadísticas. Van por el flujo
de eventos (`growth.requested` → `growth.completed`), con un solo consumidor
para los seis consejos, y sus prompts se editan desde el botón Prompts
(`growth_hooks`, `growth_retention`…).

## Portada

La pestaña **Portada** del panel de salida enseña la miniatura del video: un
título gancho en mayúsculas sobre una imagen, con una palabra en otro color. Es
lo que se ve en la cuadrícula del perfil y mientras alguien desliza el dedo,
así que se juzga en un segundo y en pequeño.

Sale sola en cuanto hay tema: el título es el tema con su palabra más larga
resaltada y la imagen, la de la primera escena con imagen (las generadas ponen
las caras arriba). Si no convence, se cambia todo desde la misma pestaña y se
repinta medio segundo después de dejar de tocar:

- **Título.** A mano —lo que va entre `*asteriscos*` sale resaltado— o entre
  los cuatro que propone el modelo del guion con «Sugerir títulos con IA»
  (`POST /api/cover/titles`, encolado como el guion). Avisa a partir de siete
  palabras: más no se leen en miniatura.
- **Diseño.** *Impacto* (texto gigante en el tercio inferior, palabra en
  amarillo), *Franja* (cada línea sobre una franja amarilla inclinada, también
  abajo) y *Titular* (arriba, palabra en una caja roja), para las imágenes con
  el motivo abajo. Los dos primeros van abajo a propósito: con el título arriba,
  en las imágenes generadas tapaba la cara.
- **Imagen.** Cualquiera de las escenas, o «IA» para pintar una solo para la
  portada con el estilo, el reparto y la semilla del video. Entra en la galería
  como cualquier imagen.

Se pinta a 1080x1920 en JPEG (de 100 a 600 KB) con PIL y la letra del motor
(`app/infrastructure/cover.py`): la imagen con más color y contraste, una sombra
detrás del texto, viñeta y el título repartido en líneas parejas, sin una
palabra huérfana al final. Todo el texto cae dentro del centro 3:4
(y ∈ [240, 1680]), que es lo que enseñan las cuadrículas de Instagram y TikTok.
Medio segundo por portada; con un clip de fondo, algo más, porque ffmpeg saca
un fotograma a tamaño completo.

La portada viaja con el render y se guarda en la ficha del video (columna
`cover` de `videos`; las bases de antes la reciben al arrancar). Al terminar el
render, «Descargar portada» baja la que se ve en pantalla, aunque se haya
retocado después; en la biblioteca, «⋯ → Descargar la portada» baja la
guardada (`GET /api/videos/{id}/cover`), y los videos de antes reciben la de
por defecto.

La cuadrícula de la biblioteca enseña esa misma portada en pequeño
(`GET /api/videos/{id}/poster`): 360 px de ancho en vertical, 480 en
horizontal. Pintarla cuesta casi un segundo, así que se pinta la primera vez y
se guarda en `data/posters/<id>.jpg` (`FilePosterStore`); después sale del
disco en milisegundos, y la interfaz le pone la fecha del video en la URL para
que el navegador la guarde sin volver a pedirla. La portada de un video no
cambia después de renderizarlo, así que no hace falta invalidarla; al borrar el
video se borra también. La letra está medida para el tamaño completo: se pinta
grande y se reduce al final (`width` en `CoverPainter.paint`). Una tarjeta cuya
portada no llega enseña el tema en su lugar.

## Descripción

El paso **5 · Descripción** prepara el texto con que se publica el video. Es lo
que leen los buscadores de YouTube, TikTok e Instagram, y cada plataforma lo
corta tras las primeras líneas («… más»), así que el orden importa: primero
las palabras clave, dichas con naturalidad; después, un resumen del video en
dos o tres frases; al final, una línea de hashtags.

«Escribir con IA» se lo encarga al modelo del guion (`POST /api/description`,
encolado como el guion) con el guion y el título de la portada delante, para
que casen. Se puede retocar o escribir a mano. Bajo el cuadro se ve lo que se
lee antes de «más» (unas 125 letras), que es donde tienen que estar las
palabras clave. Las reglas del encargo están en `app/domain/description.py`.

El tope es de 5000 caracteres, el de YouTube. Instagram corta a 2200 y TikTok
a 4000: pasarse se avisa pero no se impide. La descripción viaja con el render
y se guarda con el video (columna `description` de `videos`). Al terminar,
«Copiar descripción» la lleva al portapapeles, y en la biblioteca lo hace
«⋯ → Copiar la descripción» de cada video; «Reutilizar» la recupera.

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

**El log de eventos es la arquitectura de Kafka sin el broker.** `SqliteEventLog`
(`app/infrastructure/sqlite.py`) es un log append-only sobre la misma base SQLite, con las garantías que
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

**Las imágenes usan las mismas piezas, con consumidores que compiten.** Un
guion entero pide hasta ocho imágenes y una a una se haría largo, así que hay
tres consumidores de `illustration.requested`, cada uno con su grupo: todos ven
todos los encargos y la reserva decide quién pinta cada uno. Es la reserva que
ya evitaba redactar dos veces el mismo guion, usada a propósito. El guion visual
que precede a las imágenes es otro trabajo igual (`storyboard.requested`, con su
propio consumidor), porque lo escribe el mismo modelo que el guion y tarda lo
mismo. Viaja entero en el evento de cierre y la interfaz manda su estilo,
elementos y semilla con cada encargo de imagen: el backend no guarda estado
por video. Lo único que guarda es la biblioteca de elementos, que es de todos
los videos; un elemento que viene de ahí viaja con su id y el backend le pone
su imagen de referencia al pintar. Esas referencias son otro trabajo más
(`reference.requested`, con su consumidor), y comparten con las escenas el
pintor que revisa y repinta (`ReviewedPainter`). El desenlace de cualquier
trabajo, guion, guion visual, imagen o referencia, se consulta en
`GET /api/outcomes/{job}`.

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

**El progreso sale de moviepy.** `app/infrastructure/render_worker.py` reimplanta el ensamblado
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
`scenes`, `backgrounds`, `cover`, `description`, `render`, `library` y `writer` tienen su `model/` con
un slice y su `ui/` con los componentes. El proveedor los junta y resuelve solo
lo que ninguna feature puede resolver sola: previsualizar, renderizar y
reutilizar un video, que necesitan datos de varias a la vez. Los componentes ya
no reciben un objeto `studio` por props; piden su propio hook.

**Un panel para los pasos, no una tarjeta por paso.** Guion, voz, subtítulos,
escenas y descripción son una secuencia —la duración del guion condiciona a las
escenas, y la descripción resume el guion—, así que van numerados dentro del
mismo panel y separados por filetes. Lo que se
ajusta una vez y no se vuelve a mirar (el modelo del guion, el ajuste fino de
los subtítulos) vive en plegables, que es lo que mantiene la superficie
principal en unos pocos controles.

**Las escenas se editan en una línea de tiempo.** La barra reparte la duración
del vídeo entre las escenas, con la imagen de cada una, marca dónde acaba la
voz y apaga las que entran después. Un tramo elige su escena; cada borde se
arrastra (o se mueve con las flechas, de décima en décima o, con mayúsculas, de
segundo en segundo) para cambiar cuándo entra la siguiente, y nunca deja una
escena con menos de medio segundo ni las desordena (`draggedStart`). Una lista
de segundos de entrada no enseña ni los huecos, ni las escenas muertas, ni
cuánto dura realmente cada una; la barra sí.

**Lista compacta e inspector.** Con 30 escenas, una fila con todos sus botones
era una pared de controles. Ahora cada escena es una línea —miniatura, tramo y
lo que pide atención: pintando, animando, falló, revisar— y todo lo que se
hace con ella está en el inspector de al lado, que va pegado al bajar por la
lista. Lo que se usa poco (cambiar el fondo, verla grande, quitarla) va en
«⋯». Las casillas marcan varias para la misma transición, animarlas o
quitarlas; lo que cuesta dinero o borra pide una segunda pulsación en el sitio
(`ConfirmButton`), sin la ventana del navegador que bloquea la página.

**La animática, antes de renderizar.** La pestaña «Animática» del panel de
salida pasa las imágenes con el tiempo estimado de la voz y las transiciones
elegidas, con la frase que estaría sonando abajo. No hay voz hasta el render,
así que el ritmo es el estimado; al renderizar, cada cambio cae justo cuando la
voz dice su frase (`synced_to_voice`).

**Orientación.** La barra de arriba es un índice de los pasos con su estado
(✓ listo, ! por revisar, ◌ en curso, • falta, ○ opcional; lo decide
`web/domain/steps.ts`), y «Plegar listos» deja a la vista solo lo que falta;
el título de cada paso también lo pliega. Cada error sale junto al paso cuya
acción lo dio (`errorPlace`), no al fondo del panel de salida. Una bandeja en
la esquina enseña lo que trabaja en segundo plano —el render, las imágenes, las
animaciones— y avisa al terminar; con la pestaña en segundo plano, el título de
la página lleva el progreso del render. Las explicaciones largas que no hace
falta leer cada vez van detrás de un «?».

**Y avisa de si el clip se va a repetir.** Cuando el fondo dura menos que su
tramo, `build_background` lo encadena consigo mismo hasta cubrirlo. La interfaz
lo anticipa con la **misma fórmula del motor**, así que el número que enseña es
el que va a ocurrir; copiar la cuenta a ojo habría sido peor que no decir nada.
Las imágenes quedan fuera del aviso: no se repiten, se mueven (ver «Movimiento
de las imágenes»).

**La previsualización no renderiza vídeo.** Compone un solo fotograma con PIL:
segundos en lugar de minutos, que es lo que hace usable el ajuste de estilo.

## Estructura

```
video-studio/
├── app/                   # backend, en capas (ver «Arquitectura»)
│   ├── domain/            # reglas puras: guion, estilo, escenas, eventos, proveedores
│   ├── application/       # puertos (Protocols) y casos de uso
│   │   └── use_cases/     # scripts, render, library, backgrounds, preview, writer_settings
│   ├── infrastructure/    # SQLite, .env, ffmpeg, cola de render, worker, clientes LLM y de imagen
│   ├── api/               # FastAPI: schemas, rutas y traducción de errores
│   ├── container.py       # raíz de composición: enchufa adaptadores a casos de uso
│   └── main.py            # crea la app real (uvicorn app.main:app); las pruebas usan api/factory.py
├── tests/                 # unittest: dominio, aplicación (con dobles), SQLite, contrato HTTP
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

## Arquitectura

Backend y frontend siguen la misma idea: las reglas en el centro, el mundo
exterior detrás de puertos, y un único sitio que decide qué implementación va
en cada puerto. Las dependencias apuntan siempre hacia dentro:

```
api ──▶ application ──▶ domain
          ▲   (puertos: Protocols en application/ports.py)
          │
   infrastructure         ← solo la importa container.py (y el worker)
```

| Capa | Qué contiene | Qué no puede importar |
|---|---|---|
| `domain/` | Entidades y reglas: `clean_script`, `timeline_spans`, `CaptionStyle`, `validate_script`, convención de eventos | Nada de fuera de `domain` |
| `application/` | Casos de uso (`ScriptUseCases`, `RenderUseCases`…), `RenderJobs`, `EventConsumer` y los puertos | `infrastructure`, `api`, FastAPI, SQLite, requests |
| `infrastructure/` | Un adaptador por puerto: `SqliteEventLog`, `SubprocessRenderQueue`, `HttpScriptComposer`, `EnvCredentials`… | `api` |
| `api/` | Rutas FastAPI y modelos Pydantic; mapea `DomainError` → 400 y `NotFoundError` → 404 | `infrastructure` |

`app/container.py` es la raíz de composición: construye los adaptadores reales y
arranca los hilos de fondo cuando el servidor arranca (`lifespan`), no al
importar. Por eso `tests/test_api.py` monta la API entera sobre dobles en
memoria sin tocar SQLite ni el motor. La monta con `app/api/factory.py` y no
importa `app/main.py`: ese módulo construye el contenedor real al importarse,
así que abría `data/studio.db` en cada corrida de pruebas y, con una migración
de por medio, cambiaba la base de un servidor que estuviera en marcha.

Cambiar SQLite por un broker real es escribir otro `EventLog`; cambiar la cola
de renders por Celery es otro `RenderQueue`. Los casos de uso no se enteran.

El worker de render (`infrastructure/render_worker.py`) corre en su propio
proceso e importa solo `domain` y el puente al motor: ni FastAPI ni SQLite.

### Pruebas del backend

```bash
./.venv/bin/python -m unittest discover -s tests -t .
# Windows: .venv\Scripts\python -m unittest discover -s tests -t .
```

No necesita ffmpeg, red ni el motor: los puertos se sustituyen por los dobles
de `tests/fakes.py`. Las de SQLite usan una base temporal.

## Requisitos

Anda en Mac, Linux y Windows. El workflow `studio.yml` corre las pruebas en Mac
y Windows en cada cambio.

| | Mac | Windows |
|---|---|---|
| Python 3.11+ (probado en 3.13) | `brew install python@3.13` | `winget install Python.Python.3.13` |
| Node.js 20.9+ (22.18+ para `npm test`; probado en 24) | `brew install node` | `winget install OpenJS.NodeJS.LTS` |
| ffmpeg y ffprobe | `brew install ffmpeg` | `winget install Gyan.FFmpeg` |

Además hace falta internet para la síntesis de voz. En Windows, después de cada
`winget install` abre una terminal nueva para que tome el PATH.

Instalación en Windows (PowerShell), con el motor ya instalado al lado:

```powershell
cd video-studio
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
npm --prefix web install
py run.py
```

Notas de Windows:

- El entorno guarda los ejecutables en `.venv\Scripts`, no en `.venv/bin`.
- `.venv` y `web/node_modules` no se copian desde otra máquina: tienen binarios
  nativos. Se crean en cada una.
- El `.env` con las claves no queda restringido al usuario como en Mac
  (`chmod 600` no existe en Windows): queda con los permisos de la carpeta.
- Windows no deja borrar un archivo abierto. Si borras un video mientras se
  reproduce, la interfaz avisa; pausa y vuelve a intentar.
