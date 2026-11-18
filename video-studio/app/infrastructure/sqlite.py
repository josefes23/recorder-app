"""Historial y log de eventos en SQLite. Un solo archivo, sin servidor."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path

from app.domain.events import Event
from app.domain.illustration import Character, fold
from app.domain.saved_characters import SavedCharacter
from app.domain.video import NewVideo, Video


class Database:
    """
    Una conexión compartida y un cerrojo.

    La conexión la comparten los hilos del pool de FastAPI —cada endpoint
    síncrono corre en uno distinto— y los hilos de fondo. `check_same_thread=False`
    solo apaga el guardia de sqlite3; no hace segura la concurrencia: dos hilos
    ejecutando a la vez sobre la misma conexión devuelven filas vacías o
    revientan con «bad parameter or other API misuse». El cerrojo las
    serializa, que con un solo usuario no cuesta nada. Es reentrante por si un
    método consulta dentro de otro.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            yield self._conn

    def migrate(self, schema: str) -> None:
        with self.connection() as conn:
            conn.executescript(schema)
            conn.commit()

    def close(self) -> None:
        """Suelta el archivo. En Windows no se puede borrar mientras siga abierto."""
        with self._lock:
            self._conn.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Historial de videos
# --------------------------------------------------------------------------- #

class SqliteVideoRepository:
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
        created_at  TEXT    NOT NULL,
        cover       TEXT    NOT NULL DEFAULT '{}',
        description TEXT    NOT NULL DEFAULT ''
    );
    """

    #: Columnas que llegaron después de la tabla, con cómo crearlas en una base vieja.
    ADDED_COLUMNS = {
        "cover": "TEXT NOT NULL DEFAULT '{}'",
        "description": "TEXT NOT NULL DEFAULT ''",
    }

    def __init__(self, db: Database) -> None:
        self._db = db
        db.migrate(self.SCHEMA)
        self._add_missing_columns()

    def _add_missing_columns(self) -> None:
        """
        `CREATE TABLE IF NOT EXISTS` no toca una tabla que ya existe: las bases
        de antes de cada columna nueva la reciben aquí, con su valor vacío.
        """
        with self._db.connection() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(videos)")}
            missing = [name for name in self.ADDED_COLUMNS if name not in columns]
            for name in missing:
                conn.execute(f"ALTER TABLE videos ADD COLUMN {name} {self.ADDED_COLUMNS[name]}")
            if missing:
                conn.commit()

    def add(self, video: NewVideo) -> int:
        with self._db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO videos (topic, script, voice, style, scenes, cover, description, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (video.topic, video.script, video.voice, json.dumps(video.style),
                 json.dumps(video.scenes), json.dumps(video.cover), video.description, _now()),
            )
            conn.commit()
            return int(cur.lastrowid)

    def update(self, video_id: int, **fields) -> None:
        if not fields:
            return
        columns = ", ".join(f"{name} = ?" for name in fields)
        # Los estados llegan como StrEnum; a SQLite va el texto plano.
        values = [str(v) if isinstance(v, Enum) else v for v in fields.values()]
        with self._db.connection() as conn:
            conn.execute(f"UPDATE videos SET {columns} WHERE id = ?", (*values, video_id))
            conn.commit()

    def get(self, video_id: int) -> Video | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        return _row_to_video(row) if row else None

    def list(self, limit: int = 60) -> list[Video]:
        with self._db.connection() as conn:
            rows = conn.execute("SELECT * FROM videos ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [_row_to_video(r) for r in rows]

    def remove(self, video_id: int) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
            conn.commit()


def _row_to_video(row: sqlite3.Row) -> Video:
    data = dict(row)
    for field in ("style", "scenes", "cover"):
        try:
            data[field] = json.loads(data[field]) if data.get(field) else {}
        except (TypeError, json.JSONDecodeError):
            data[field] = {}
    return Video(**data)


# --------------------------------------------------------------------------- #
# Biblioteca de elementos
# --------------------------------------------------------------------------- #

class SqlitePromptStore:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS prompt_overrides (
        id          TEXT PRIMARY KEY,
        body        TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    );
    """

    def __init__(self, db: Database) -> None:
        self._db = db
        db.migrate(self.SCHEMA)

    def all(self) -> dict[str, str]:
        with self._db.connection() as conn:
            return {row["id"]: row["body"] for row in conn.execute("SELECT id, body FROM prompt_overrides")}

    def set(self, prompt_id: str, body: str) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "INSERT INTO prompt_overrides (id, body, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET body = excluded.body, updated_at = excluded.updated_at",
                (prompt_id, body, _now()),
            )
            conn.commit()

    def remove(self, prompt_id: str) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM prompt_overrides WHERE id = ?", (prompt_id,))
            conn.commit()


class SqliteCharacterRepository:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS characters (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        folded      TEXT    NOT NULL UNIQUE,
        traits      TEXT    NOT NULL,
        kind        TEXT    NOT NULL DEFAULT 'persona',
        reference   TEXT,
        created_at  TEXT    NOT NULL,
        updated_at  TEXT    NOT NULL
    );
    """

    def __init__(self, db: Database) -> None:
        self._db = db
        db.migrate(self.SCHEMA)

    def list(self) -> list[SavedCharacter]:
        # Lo último guardado o repintado primero: es lo que se ofrece al guion visual.
        with self._db.connection() as conn:
            rows = conn.execute("SELECT * FROM characters ORDER BY updated_at DESC, id DESC").fetchall()
        return [_row_to_character(r) for r in rows]

    def get(self, character_id: int) -> SavedCharacter | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM characters WHERE id = ?", (character_id,)).fetchone()
        return _row_to_character(row) if row else None

    def find(self, name: str) -> SavedCharacter | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM characters WHERE folded = ?", (fold(name),)).fetchone()
        return _row_to_character(row) if row else None

    def upsert(self, character: Character) -> SavedCharacter:
        """Guarda por nombre: el mismo nombre actualiza rasgos y tipo y conserva su referencia."""
        now = _now()
        with self._db.connection() as conn:
            conn.execute(
                "INSERT INTO characters (name, folded, traits, kind, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(folded) DO UPDATE SET name = excluded.name, traits = excluded.traits, "
                "kind = excluded.kind, updated_at = excluded.updated_at",
                (character.name, fold(character.name), character.traits, character.kind, now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM characters WHERE folded = ?", (fold(character.name),)).fetchone()
        return _row_to_character(row)

    def set_reference(self, character_id: int, reference: str | None) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "UPDATE characters SET reference = ?, updated_at = ? WHERE id = ?",
                (reference, _now(), character_id),
            )
            conn.commit()

    def remove(self, character_id: int) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))
            conn.commit()


def _row_to_character(row: sqlite3.Row) -> SavedCharacter:
    data = dict(row)
    data.pop("folded", None)
    return SavedCharacter(**data)


# --------------------------------------------------------------------------- #
# Log de eventos
# --------------------------------------------------------------------------- #

class SqliteEventLog:
    """
    Log append-only con posiciones y consumidores que confirman avance.

    Es la arquitectura de Kafka sin el broker. Aquí no hay uno a propósito: esto
    corre en localhost para un solo usuario, y levantar un servicio aparte para
    redactar un guion sería mantenimiento a cambio de nada. Lo que sí se respeta
    son las garantías, que son las que evitan perder trabajos:

    - El log solo crece. Un evento es un hecho ya ocurrido y nunca se reescribe.
    - Cada evento tiene un `offset` monótono: esa es la posición del consumidor.
    - La clave agrupa los eventos de un mismo trabajo, como la clave de partición.
    - Entrega al menos una vez: el consumidor confirma su offset DESPUÉS de
      trabajar, así que un corte reprocesa pero no pierde.
    - Los offsets de cada grupo se guardan, así que al reiniciar se sigue donde
      se estaba en vez de volver al principio del log.

    Cambiarlo por un broker de verdad es escribir otro adaptador del puerto
    `EventLog`; la aplicación no se entera.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS events (
        "offset"   INTEGER PRIMARY KEY AUTOINCREMENT,
        topic      TEXT NOT NULL,
        key        TEXT,
        payload    TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS events_topic ON events (topic, "offset");
    CREATE INDEX IF NOT EXISTS events_key ON events (key);

    CREATE TABLE IF NOT EXISTS consumer_offsets (
        consumer_group TEXT PRIMARY KEY,
        "offset"       INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS claims (
        key        TEXT PRIMARY KEY,
        claimed_at REAL NOT NULL
    );
    """

    # Cuánto vale una reserva. Pasado ese plazo se da por muerto al consumidor
    # que la tenía y otro puede retomar el trabajo. Tiene que superar lo que
    # puede tardar el más lento de los proveedores.
    LEASE_SECONDS = 600

    # Cuántos eventos se conservan. El log es historial, no almacenamiento: los
    # guiones terminados ya viven en el estado de la interfaz.
    RETENTION = 2000

    def __init__(self, db: Database) -> None:
        self._db = db
        db.migrate(self.SCHEMA)
        # Despierta a los consumidores en cuanto se publica, en vez de sondear.
        self._published = threading.Condition()

    def publish(self, topic: str, key: str | None, payload: dict) -> Event:
        created_at = _now()
        with self._db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO events (topic, key, payload, created_at) VALUES (?, ?, ?, ?)",
                (topic, key, json.dumps(payload, ensure_ascii=False), created_at),
            )
            conn.commit()
            offset = int(cur.lastrowid)

        with self._published:
            self._published.notify_all()

        return Event(offset, topic, key, payload, created_at)

    def read_after(self, offset: int, topics: tuple[str, ...] = (), limit: int = 200) -> list[Event]:
        sql = 'SELECT * FROM events WHERE "offset" > ?'
        params: list = [offset]
        if topics:
            sql += f" AND topic IN ({', '.join('?' * len(topics))})"
            params.extend(topics)
        sql += ' ORDER BY "offset" LIMIT ?'
        params.append(limit)

        with self._db.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_event(r) for r in rows]

    def wait_for(self, offset: int, timeout: float, topics: tuple[str, ...] = ()) -> list[Event]:
        """Como `read_after`, pero espera hasta `timeout` si todavía no hay nada.

        Bloquea el hilo: quien lo llame desde código asíncrono debe hacerlo en
        el pool de hilos, no en el bucle de eventos.
        """
        deadline = time.monotonic() + timeout
        with self._published:
            while True:
                batch = self.read_after(offset, topics)
                if batch:
                    return batch
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return []
                self._published.wait(remaining)

    def last_offset(self) -> int:
        with self._db.connection() as conn:
            row = conn.execute('SELECT MAX("offset") AS head FROM events').fetchone()
        return int(row["head"] or 0)

    def by_key(self, key: str, topics: tuple[str, ...] = ()) -> list[Event]:
        sql = "SELECT * FROM events WHERE key = ?"
        params: list = [key]
        if topics:
            sql += f" AND topic IN ({', '.join('?' * len(topics))})"
            params.extend(topics)
        sql += ' ORDER BY "offset"'

        with self._db.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_event(r) for r in rows]

    def settled(self, key: str, topics: tuple[str, ...]) -> bool:
        with self._db.connection() as conn:
            row = conn.execute(
                f'SELECT 1 FROM events WHERE key = ? AND topic IN ({", ".join("?" * len(topics))}) LIMIT 1',
                (key, *topics),
            ).fetchone()
        return row is not None

    def claim(self, key: str) -> bool:
        """Reserva un trabajo para este consumidor. False si ya lo tiene otro.

        Hace falta porque puede haber más de un backend contra la misma base
        —pasa sin querer al levantar `./run.sh` y `npm run dev` a la vez—, y
        sin esto los dos redactan el mismo guion.

        Va en una sola sentencia a propósito: el cerrojo del proceso no vale
        entre procesos, así que la exclusión tiene que salir de SQLite. La
        reserva caduca para que un consumidor muerto no bloquee el trabajo
        para siempre.
        """
        now = time.time()
        with self._db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO claims (key, claimed_at) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET claimed_at = excluded.claimed_at "
                "WHERE claims.claimed_at < ?",
                (key, now, now - self.LEASE_SECONDS),
            )
            conn.commit()
            return cur.rowcount > 0

    def committed_offset(self, consumer_group: str) -> int:
        with self._db.connection() as conn:
            row = conn.execute(
                'SELECT "offset" FROM consumer_offsets WHERE consumer_group = ?',
                (consumer_group,),
            ).fetchone()
        return int(row["offset"]) if row else 0

    def commit(self, consumer_group: str, offset: int) -> None:
        with self._db.connection() as conn:
            conn.execute(
                'INSERT INTO consumer_offsets (consumer_group, "offset") VALUES (?, ?) '
                'ON CONFLICT(consumer_group) DO UPDATE SET "offset" = excluded."offset"',
                (consumer_group, offset),
            )
            conn.commit()

    def prune(self) -> int:
        """Retención por número de eventos. Devuelve cuántos se tiraron."""
        with self._db.connection() as conn:
            cur = conn.execute(
                'DELETE FROM events WHERE "offset" <= (SELECT MAX("offset") FROM events) - ?',
                (self.RETENTION,),
            )
            conn.commit()
            return cur.rowcount or 0


def _row_to_event(row: sqlite3.Row) -> Event:
    try:
        payload = json.loads(row["payload"])
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return Event(row["offset"], row["topic"], row["key"], payload, row["created_at"])
