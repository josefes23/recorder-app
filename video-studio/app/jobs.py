"""
Cola de renders: un trabajo a la vez, en un proceso aparte.

Es de un solo usuario, así que no hace falta Redis ni Celery — un hilo con una
cola FIFO y `subprocess` cubre el caso y no añade servicios que mantener.
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from app import db
from app.engine import DATA, OUTPUTS, ROOT, slugify

JOBS_DIR = DATA / "jobs"
_queue: queue.Queue[int] = queue.Queue()
_state: dict[int, dict] = {}
_lock = threading.Lock()


def status(video_id: int) -> dict:
    with _lock:
        return dict(_state.get(video_id, {"status": "unknown"}))


def all_active() -> list[dict]:
    with _lock:
        return [
            {"id": vid, **info}
            for vid, info in _state.items()
            if info.get("status") in ("queued", "running")
        ]


def _set(video_id: int, **fields) -> None:
    with _lock:
        _state.setdefault(video_id, {}).update(fields)


def enqueue(video_id: int, spec: dict) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    spec["output"] = str(OUTPUTS / f"{slugify(spec.get('topic', ''))}_{stamp}.mp4")
    (JOBS_DIR / f"{video_id}.json").write_text(
        json.dumps(spec, ensure_ascii=False), encoding="utf-8"
    )

    _set(video_id, status="queued", progress=0.0, message="En cola", phase="queued")
    db.update_video(video_id, status="queued")
    _queue.put(video_id)


def _run(video_id: int) -> None:
    job_file = JOBS_DIR / f"{video_id}.json"
    _set(video_id, status="running", progress=0.01, message="Arrancando…")
    db.update_video(video_id, status="running")

    process = subprocess.Popen(
        [sys.executable, "-m", "app.render_worker", str(job_file)],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )

    result: dict = {}
    for line in process.stdout:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("done") or event.get("error"):
            result = event
            continue
        _set(video_id,
             progress=round(float(event.get("progress", 0)), 3),
             message=event.get("message", ""),
             phase=event.get("phase", ""))

    stderr = (process.stderr.read() or "").strip()
    process.wait()

    if result.get("done"):
        _set(video_id, status="done", progress=1.0, message="Listo",
             output=result["output"])
        db.update_video(
            video_id, status="done", filename=result["output"],
            duration=result.get("duration"), size_mb=result.get("size_mb"),
            captions=result.get("captions"), error=None,
        )
        return

    # El worker escribe su propio error; stderr es el respaldo si murió antes.
    detail = result.get("error") or stderr[-800:] or f"El proceso terminó con código {process.returncode}"
    _set(video_id, status="error", message=detail)
    db.update_video(video_id, status="error", error=detail)


def _worker() -> None:
    while True:
        video_id = _queue.get()
        try:
            _run(video_id)
        except Exception as exc:  # noqa: BLE001 - el hilo no debe morir nunca
            _set(video_id, status="error", message=f"{type(exc).__name__}: {exc}")
            db.update_video(video_id, status="error", error=str(exc))
        finally:
            _queue.task_done()


def start() -> None:
    threading.Thread(target=_worker, daemon=True, name="render-worker").start()
