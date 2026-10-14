# Fuentes de los subtítulos

Los subtítulos quemados usan las fuentes de esta carpeta, no las del sistema:
así salen iguales en Windows, Linux y Mac (Linux no trae Arial). El nombre de
la familia va en `SUBTITLES["style"]["font"]` de `config.py`.

| Archivo | Fuente | Origen | Licencia |
|---|---|---|---|
| `LiberationSans-Bold.ttf`, `LiberationSans-Regular.ttf` | Liberation Sans 2.1.5 | [liberationfonts/liberation-fonts](https://github.com/liberationfonts/liberation-fonts/releases/tag/2.1.5) | SIL Open Font License 1.1 (`LICENSE.txt`) |

Liberation Sans tiene las mismas medidas que Arial: los cortes y el tamaño de
los subtítulos no cambian respecto de los videos hechos con Arial.

Para usar otra fuente, sumá sus `.ttf` acá con su licencia (tiene que permitir
uso comercial), anotala en esta tabla y cambiá el nombre de la familia en
`config.py`, en un PR aparte: cambia los subtítulos de todos los videos.
