"""
Log de eventos: append-only, con posiciones y consumidores que confirman avance.

Es la arquitectura de Kafka sin el broker. Aquí no hay uno a propósito: esto
corre en localhost para un solo usuario, y levantar un servicio aparte para
redactar un guion sería mantenimiento a cambio de nada — la misma razón por la
que la cola de renders es un hilo y no Celery. Lo que sí se respeta son las
garantías, que son las que evitan perder trabajos:

- El log solo crece. Un evento es un hecho ya ocurrido y nunca se reescribe.
- Cada evento tiene un `offset` monótono: esa es la posición del consumidor.
- La clave agrupa los eventos de un mismo trabajo, como la clave de partición.
- Entrega **al menos una vez**: el consumidor confirma su offset DESPUÉS de
  trabajar, así que un corte reprocesa pero no pierde. Por eso el consumidor
  tiene que ser idempotente — para eso está `settled()`.
- Los offsets de cada grupo se guardan, así que al reiniciar se sigue donde se
  estaba en vez de volver al principio del log.

Cambiarlo por un broker de verdad es reescribir `publish()` y `read_after()`;
nadie más toca SQLite.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from app import db

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

# Cuánto vale una reserva. Pasado ese plazo se da por muerto al consumidor que
# la tenía y otro puede retomar el trabajo. Tiene que superar lo que puede
# tardar el más lento de los proveedores.
LEASE_SECONDS = 600

# Cuántos eventos se conservan. El log es historial, no almacenamiento: los
# guiones terminados ya viven en el estado de la interfaz.
RETENTION = 2000

# Despierta a los consumidores en cuanto se publica, en vez de sondear.
_published = threading.Condition()

with db.connection() as _conn:
    _conn.executescript(SCHEMA)
    _conn.commit()


@dataclass(frozen=True)
class Event:
    offset: int
    topic: str
    key: str | None
    payload: dict
    created_at: str

    def as_dict(self) -> dict:
        return {
            "offset": self.offset,
            "topic": self.topic,
            "key": self.key,
            "payload": self.payload,
            "created_at": self.created_at,
        }


def _row_to_event(row) -> Event:
    try:
        payload = json.loads(row["payload"])
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return Event(row["offset"], row["topic"], row["key"], payload, row["created_at"])


# --------------------------------------------------------------------------- #
# Productor
# --------------------------------------------------------------------------- #

def publish(topic: str, key: str | None, payload: dict) -> Event:
    """Añade un hecho al final del log y despierta a quien esté esperando."""
    created_at = datetime.now().isoformat(timespec="seconds")
    with db.connection() as conn:
        cur = conn.execute(
            'INSERT INTO events (topic, key, payload, created_at) VALUES (?, ?, ?, ?)',
            (topic, key, json.dumps(payload, ensure_ascii=False), created_at),
        )
        conn.commit()
        offset = int(cur.lastrowid)

    with _published:
        _published.notify_all()

    return Event(offset, topic, key, payload, created_at)


# --------------------------------------------------------------------------- #
# Consumo
# --------------------------------------------------------------------------- #

def read_after(offset: int, topics: tuple[str, ...] = (), limit: int = 200) -> list[Event]:
    """Los eventos posteriores a `offset`, en orden."""
    sql = 'SELECT * FROM events WHERE "offset" > ?'
    params: list = [offset]
    if topics:
        sql += f" AND topic IN ({', '.join('?' * len(topics))})"
        params.extend(topics)
    sql += ' ORDER BY "offset" LIMIT ?'
    params.append(limit)

    with db.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_event(r) for r in rows]


def wait_for(offset: int, timeout: float, topics: tuple[str, ...] = ()) -> list[Event]:
    """Como `read_after`, pero espera hasta `timeout` si todavía no hay nada.

    Bloquea el hilo: quien lo llame desde código asíncrono debe hacerlo en el
    pool de hilos, no en el bucle de eventos.
    """
    deadline = time.monotonic() + timeout
    with _published:
        while True:
            batch = read_after(offset, topics)
            if batch:
                return batch
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return []
            _published.wait(remaining)


def last_offset() -> int:
    """Cabeza del log: desde aquí escucha quien solo quiere lo que venga."""
    with db.connection() as conn:
        row = conn.execute('SELECT MAX("offset") AS head FROM events').fetchone()
    return int(row["head"] or 0)


def claim(key: str, lease: float = LEASE_SECONDS) -> bool:
    """Reserva un trabajo para este consumidor. False si ya lo tiene otro.

    Hace falta porque puede haber más de un backend contra la misma base —pasa
    sin querer al levantar `./run.sh` y `npm run dev` a la vez—, y sin esto los
    dos redactan el mismo guion: doble espera, doble gasto y dos respuestas
    compitiendo por publicarse.

    Va en una sola sentencia a propósito: el cerrojo del módulo solo protege
    dentro de un proceso, así que la exclusión entre procesos tiene que salir
    de SQLite. La reserva caduca para que un consumidor muerto no bloquee el
    trabajo para siempre, que es justo lo que la entrega al menos una vez
    intenta evitar.
    """
    now = time.time()
    with db.connection() as conn:
        cur = conn.execute(
            "INSERT INTO claims (key, claimed_at) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET claimed_at = excluded.claimed_at "
            "WHERE claims.claimed_at < ?",
            (key, now, now - lease),
        )
        conn.commit()
        return cur.rowcount > 0


def by_key(key: str, topics: tuple[str, ...] = ()) -> list[Event]:
    """Los eventos de un trabajo, en orden. El log es consultable, no solo un flujo."""
    sql = "SELECT * FROM events WHERE key = ?"
    params: list = [key]
    if topics:
        sql += f" AND topic IN ({', '.join('?' * len(topics))})"
        params.extend(topics)
    sql += ' ORDER BY "offset"'

    with db.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_event(r) for r in rows]


def settled(key: str, topics: tuple[str, ...]) -> bool:
    """¿Ya hay un evento final para esta clave?

    Es el guardia de idempotencia: con entrega al menos una vez, un trabajo
    puede volver a entregarse tras un corte y no debe ejecutarse dos veces.
    """
    with db.connection() as conn:
        row = conn.execute(
            f'SELECT 1 FROM events WHERE key = ? AND topic IN ({", ".join("?" * len(topics))}) LIMIT 1',
            (key, *topics),
        ).fetchone()
    return row is not None


# --------------------------------------------------------------------------- #
# Offsets por grupo
# --------------------------------------------------------------------------- #

def committed_offset(consumer_group: str) -> int:
    with db.connection() as conn:
        row = conn.execute(
            'SELECT "offset" FROM consumer_offsets WHERE consumer_group = ?',
            (consumer_group,),
        ).fetchone()
    return int(row["offset"]) if row else 0


def commit(consumer_group: str, offset: int) -> None:
    """Se confirma después de trabajar, nunca antes: así se reprocesa en vez de perder."""
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO consumer_offsets (consumer_group, \"offset\") VALUES (?, ?) "
            "ON CONFLICT(consumer_group) DO UPDATE SET \"offset\" = excluded.\"offset\"",
            (consumer_group, offset),
        )
        conn.commit()


def prune(keep: int = RETENTION) -> int:
    """Retención por número de eventos. Devuelve cuántos se tiraron."""
    with db.connection() as conn:
        cur = conn.execute(
            'DELETE FROM events WHERE "offset" <= '
            '(SELECT MAX("offset") FROM events) - ?',
            (keep,),
        )
        conn.commit()
        return cur.rowcount or 0
