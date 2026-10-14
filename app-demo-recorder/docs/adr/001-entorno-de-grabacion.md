# ADR 001: Dónde y contra qué se graban los videos finales

**Estado:** Aceptado · **Fecha:** 2026-09-29

## Contexto

El grabador corre en Windows, Linux y Mac, pero el video que sale dependía de
la máquina de quien grababa:

- **Datos.** Las escenas tenían IDs escritos (`/league/cmuejep…/config/venues`)
  que solo existían en la base local de una persona. En otra máquina, o
  contra staging, fallaban en el primer paso.
- **Dibujo.** Chromium no suaviza el texto igual en los tres sistemas, los
  subtítulos pedían Arial (Linux no la trae) y los cuadros por segundo
  dependen de la carga de la máquina: en una misma Mac, la toma de celular dio
  11 cps y después 17.
- **Trazabilidad.** El video subido a la carpeta compartida no quedaba atado
  a la versión de la escena ni de la app.
- **Voz.** edge-tts usa el "leer en voz alta" de Edge, que no es un servicio
  oficial: puede dejar de andar sin aviso y no está pensado para contenido comercial.

## Opciones

| | A. Cada uno graba en local | B. Staging compartido, grabación local | C. Staging + el CI graba los finales | D. Contenedor Docker |
|---|---|---|---|---|
| Datos iguales | No | Sí | Sí | No (lo resuelve B) |
| Dibujo igual | No | No | Sí | Sí |
| Video ligado al commit | No | No | Sí | No |
| Costo | Ninguno | Script de datos demo | Secretos + workflow | Imagen, Docker Desktop, red hacia la app local |
| Riesgo | Escenas que solo andan en una máquina | Tomas simultáneas que se pisan | Runners lentos: el celular puede quedar debajo de 12 cps | Más lento en Mac/Windows (VM sin GPU); `--ver` y `APP_DEV_CMD` no andan |

## Decisión

**B + C.** Staging con una liga demo como único entorno de datos, y los
videos finales grabados por el workflow `escenas.yml`. En local se escriben y
se prueban escenas (borradores), con `--ver` y todo lo demás.

Docker (D) se evaluó y se descartó por ahora: iguala el dibujo, pero no los
datos, y complica el trabajo diario con los asistentes. C da la misma
igualdad para los finales sin cambiar cómo trabaja cada uno.

Complementos:

- Las rutas de las escenas usan los datos del login (`{liga}`), nunca IDs.
- Los subtítulos usan una fuente versionada (`fonts/`, Liberation Sans, con
  las medidas de Arial) en vez de la del sistema.
- Cada video trae un `.json` con el commit, la escena, la app, el sistema, la
  voz y los cuadros por segundo; el commit también va en los metadatos del `.mp4`.
- Los finales usan Azure AI Speech (`--proveedor-voz azure`) si el repo tiene la
  clave; edge-tts queda para borradores.
- El mismo workflow corre cada día hábil una prueba rápida de todas las
  escenas contra staging, para enterarse cuando un cambio de la app rompe una.

## Consecuencias

- Una escena anda igual para todos, y cualquiera puede revisarla o regrabarla.
- Hay que mantener un script de datos demo en el repo de la app (tabla "Datos
  demo" en `CONTRIBUTING.md`) y una cuenta demo con permisos mínimos.
- Staging tiene que estar accesible desde GitHub Actions.
- **Revisar:** en los primeros runs de `escenas.yml`, mirar los cps de
  celular en el log. Si quedan debajo de 12, grabar los finales con
  `sistema: macos-latest` o bajar `scale` a 1.5 en el perfil de celular.
