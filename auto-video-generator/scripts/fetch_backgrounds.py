#!/usr/bin/env python3
"""
Descarga clips verticales de Pexels a assets/backgrounds/.

Necesita una API key gratuita de https://www.pexels.com/api/, en el archivo .env
de la raíz como PEXELS_API_KEY, en la variable de entorno del mismo nombre o vía
--api-key. Sin credenciales la API solo responde a unos pocos términos comunes de
una palabra que tiene cacheados, y deja de hacerlo tras unas pocas peticiones
desde la misma IP.

Licencia Pexels: uso gratuito, también comercial, sin atribución obligatoria.

Uso:
  python scripts/fetch_backgrounds.py --query "abstract dark" --count 5
  python scripts/fetch_backgrounds.py --query "coffee" --list
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BACKGROUNDS_DIR = ROOT / "assets" / "backgrounds"
API_URL = "https://api.pexels.com/videos/search"

TARGET_WIDTH = 1080          # ancho objetivo para 9:16
REQUEST_TIMEOUT = 30


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "bg"


def pick_file(video: dict, max_bytes: int) -> dict | None:
    """
    Elige la versión vertical más adecuada de un vídeo.

    Preferimos el archivo más pequeño que llegue a 1080 de ancho: subir de ahí
    solo añade megas, porque el render recorta a 1080x1920 de todos modos.
    Algunos clips publican un 1080p con bitrate desmedido (175 MB para 60 s),
    así que descartamos los que pasen del tope antes de elegir.
    """
    vertical = [
        f for f in video.get("video_files", [])
        if f.get("file_type") == "video/mp4"
        and f.get("width") and f.get("height")
        and f["height"] > f["width"]
    ]
    if not vertical:
        return None
    affordable = [f for f in vertical if f.get("size", 0) <= max_bytes] or vertical
    big_enough = [f for f in affordable if f["width"] >= TARGET_WIDTH]
    if big_enough:
        return min(big_enough, key=lambda f: f["width"])
    return max(affordable, key=lambda f: f["width"])


def search(query: str, count: int, min_duration: int, api_key: str | None) -> list[dict]:
    headers = {"Authorization": api_key} if api_key else {}
    params = {
        "query": query,
        "orientation": "portrait",
        "per_page": min(max(count * 3, 15), 80),  # margen para descartar cortos
    }
    try:
        r = requests.get(API_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        sys.exit(f"ERROR: no se pudo contactar con Pexels: {e}")

    if r.status_code == 401:
        if api_key:
            sys.exit("ERROR: Pexels rechazó la API key. Revísala en pexels.com/api.")
        # Sin credenciales Pexels solo responde a los términos que tiene cacheados
        # (palabras sueltas y comunes: nature, ocean, city, abstract, coffee...).
        # Cualquier otra búsqueda devuelve 401.
        sys.exit(
            f"ERROR: Pexels pide autenticación para la búsqueda '{query}'.\n\n"
            "  Opciones:\n"
            "  1. Consigue una API key gratuita en https://www.pexels.com/api/\n"
            "     y pásala con --api-key TU_KEY (o guárdala en el archivo .env\n"
            "     de la raíz como PEXELS_API_KEY=TU_KEY).\n"
            "  2. O prueba con un término común de una sola palabra en inglés:\n"
            "     nature, ocean, city, forest, abstract, coffee, sky, rain."
        )
    if r.status_code == 429:
        sys.exit("ERROR: límite de peticiones de Pexels alcanzado. Prueba más tarde "
                 "o usa una API key propia (--api-key).")
    if not r.ok:
        sys.exit(f"ERROR: Pexels devolvió HTTP {r.status_code}: {r.text[:200]}")

    videos = r.json().get("videos", [])
    keep = [v for v in videos if v.get("duration", 0) >= min_duration]
    if not keep:
        sys.exit(f"Sin resultados verticales de al menos {min_duration}s para '{query}'. "
                 f"Prueba otra búsqueda o baja --min-duration.")
    return keep


def download(url: str, dest: Path) -> int:
    with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT) as r:
        r.raise_for_status()
        # Content-Length de la respuesta, no el "size" del catálogo: ese último
        # describe otra variante del clip y no cuadra con el archivo servido.
        expected = int(r.headers.get("Content-Length") or 0)
        tmp = dest.with_suffix(".part")
        written = 0
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
                written += len(chunk)
        if expected and written != expected:
            tmp.unlink(missing_ok=True)
            raise requests.RequestException(
                f"descarga incompleta: {written} de {expected} bytes"
            )
        tmp.rename(dest)  # renombrado atómico: nunca dejamos un .mp4 a medias
    return written


def resolve_api_key(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    if os.environ.get("PEXELS_API_KEY"):
        return os.environ["PEXELS_API_KEY"]
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "PEXELS_API_KEY":
                return value.strip().strip("'\"") or None
    return None


def main() -> None:
    p = argparse.ArgumentParser(description="Descarga fondos verticales de Pexels.")
    p.add_argument("--query", required=True, help="Búsqueda, ej. 'abstract dark' o 'ocean'.")
    p.add_argument("--count", type=int, default=5, help="Cuántos clips descargar (def: 5).")
    p.add_argument("--min-duration", type=int, default=8, help="Duración mínima en s (def: 8).")
    p.add_argument("--max-size", type=int, default=100,
                   help="Tamaño máximo por clip en MB (def: 100).")
    p.add_argument("--api-key", help="API key de Pexels (opcional).")
    p.add_argument("--list", action="store_true", help="Solo listar, sin descargar.")
    args = p.parse_args()

    BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)
    videos = search(args.query, args.count, args.min_duration, resolve_api_key(args.api_key))

    print(f"\n{len(videos)} clips verticales encontrados para \"{args.query}\"\n")
    slug = slugify(args.query)
    downloaded = 0

    for video in videos:
        if downloaded >= args.count:
            break
        chosen = pick_file(video, args.max_size * 1_000_000)
        if not chosen:
            continue

        dest = BACKGROUNDS_DIR / f"{slug}_{video['id']}.mp4"
        label = (f"{chosen['width']}x{chosen['height']}  {video['duration']:>3}s  "
                 f"{chosen['size'] / 1e6:5.1f} MB  {video['user']['name']}")

        if args.list:
            print(f"  {label}\n    {video['url']}")
            downloaded += 1
            continue
        if dest.exists():
            print(f"  ya estaba: {dest.name}")
            continue

        print(f"  descargando {dest.name}  ({label})", flush=True)
        try:
            size = download(chosen["link"], dest)
        except requests.RequestException as e:
            print(f"    fallo: {e}")
            dest.with_suffix(".part").unlink(missing_ok=True)
            continue
        print(f"    ok, {size / 1e6:.1f} MB")
        downloaded += 1

    if args.list:
        print(f"\n{downloaded} listados. Quita --list para descargarlos.")
        return

    total = len(list(BACKGROUNDS_DIR.glob("*.mp4")))
    print(f"\n✅ {downloaded} clips nuevos. {total} fondos en assets/backgrounds/")
    print("   Se elegirá uno al azar en cada video que generes.\n")


if __name__ == "__main__":
    main()
