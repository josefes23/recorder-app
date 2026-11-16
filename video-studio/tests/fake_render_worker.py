"""
Worker de mentira para las pruebas de la cola de renders.

Repite el tema del trabajo en un progreso y en el error final, así viajan por
el pipe caracteres que cp1252 (la página de códigos de Windows) no tiene.
"""

import json
import sys
from pathlib import Path

job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(json.dumps({"phase": "voice", "progress": 0.5, "message": job["topic"]}, ensure_ascii=False), flush=True)
print(json.dumps({"error": f"falló: {job['topic']}"}, ensure_ascii=False), flush=True)
