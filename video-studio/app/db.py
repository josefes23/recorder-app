"""Historial en SQLite. Un solo archivo, sin servidor."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.engine import DATA

DB_PATH = DATA / "studio.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT    NOT NULL,
    script      TEXT    NOT NULL,
    voice       TEXT    NOT NULL,
    style       TEXT    NOT NULL,
    scenes      TEXT    NOT NULL,
    filename    TEXT,
    duration    REAL,
    size_mb     REAL,
    captions    INTEGER,
    status      TEXT    NOT NULL DEFAULT 'queued',
    error       TEXT,
    created_at  TEXT    NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


_conn = connect()

# La conexión la comparten los hilos del pool de FastAPI —cada endpoint síncrono
# corre en uno distinto— y el hilo de la cola de renders. `check_same_thread=False`
# solo apaga el guardia de sqlite3; no hace segura la concurrencia: dos hilos
# ejecutando a la vez sobre la misma conexión devuelven filas vacías o revientan
# con «bad parameter or other API misuse». El cerrojo las serializa, que con un
# solo usuario no cuesta nada. Es reentrante porque delete_video consulta antes
# de borrar.
_lock = threading.RLock()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Acceso serializado a la conexión para otros módulos (el log de eventos).

    Comparte cerrojo con el resto del historial: hay una sola conexión y un solo
    archivo, así que la exclusión tiene que ser la misma o volvemos al fallo.
    """
    with _lock:
        yield _conn


def create_video(topic: str, script: str, voice: str, style: dict, scenes: list) -> int:
    with _lock:
        cur = _conn.execute(
            "INSERT INTO videos (topic, script, voice, style, scenes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (topic, script, voice, json.dumps(style), json.dumps(scenes),
             datetime.now().isoformat(timespec="seconds")),
        )
        _conn.commit()
        return int(cur.lastrowid)


def update_video(video_id: int, **fields) -> None:
    if not fields:
        return
    columns = ", ".join(f"{k} = ?" for k in fields)
    with _lock:
        _conn.execute(f"UPDATE videos SET {columns} WHERE id = ?", (*fields.values(), video_id))
        _conn.commit()


def get_video(video_id: int) -> dict | None:
    with _lock:
        row = _conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_videos(limit: int = 60) -> list[dict]:
    with _lock:
        rows = _conn.execute(
            "SELECT * FROM videos ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_video(video_id: int) -> None:
    # Consulta, borrado del archivo y borrado de la fila van juntos: si no, dos
    # peticiones simultáneas podrían leer la misma fila y borrar dos veces.
    with _lock:
        video = get_video(video_id)
        if video and video.get("filename"):
            Path(video["filename"]).unlink(missing_ok=True)
        _conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        _conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    for field in ("style", "scenes"):
        try:
            data[field] = json.loads(data[field]) if data.get(field) else {}
        except (TypeError, json.JSONDecodeError):
            data[field] = {}
    return data
