import sys


def utf8_console() -> None:
    """Salida en UTF-8 en todos los sistemas.

    En Windows, cuando la salida va a un pipe (Claude Code, CI) Python usa la
    página de códigos local (cp1252) y un "●" o "→" en un print corta el programa.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
