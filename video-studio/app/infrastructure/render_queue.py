"""
Cola de renders: un trabajo a la vez, en un proceso aparte.

Es de un solo usuario, así que no hace falta Redis ni Celery — un hilo con una
cola FIFO y `subprocess` cubre el caso y no añade servicios que mantener. El
worker va en su propio proceso porque un render de varios minutos bloquearía
el servidor, y así su progreso se lee línea a línea por stdout.
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from app.application.ports import RenderListener
from app.domain.video import RenderResult, RenderSpec, output_filename

WORKER_MODULE = "app.infrastructure.render_worker"


class SubprocessRenderQueue:
    def __init__(
        self,
        jobs_dir: Path,
        outputs_dir: Path,
        root: Path,
        listener: RenderListener,
        python: str = sys.executable,
    ) -> None:
        self._jobs_dir = jobs_dir
        self._outputs = outputs_dir
        self._root = root
        self._listener = listener
        self._python = python
        self._queue: queue.Queue[int] = queue.Queue()

    def enqueue(self, video_id: int, spec: RenderSpec) -> None:
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._outputs.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job = spec.as_dict()
        job["output"] = str(self._outputs / output_filename(spec.topic, stamp))
        self._job_file(video_id).write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")

        self._listener.queued(video_id)
        self._queue.put(video_id)

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self._worker, daemon=True, name="render-queue")
        thread.start()
        return thread

    def _job_file(self, video_id: int) -> Path:
        return self._jobs_dir / f"{video_id}.json"

    def _run(self, video_id: int) -> None:
        self._listener.started(video_id)

        process = subprocess.Popen(
            [self._python, "-m", WORKER_MODULE, str(self._job_file(video_id))],
            cwd=str(self._root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )

        result: dict = {}
        assert process.stdout is not None
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
            self._listener.progressed(
                video_id,
                float(event.get("progress", 0)),
                event.get("message", ""),
                event.get("phase", ""),
            )

        stderr = (process.stderr.read() if process.stderr else "") or ""
        process.wait()

        if result.get("done"):
            self._listener.finished(video_id, RenderResult.from_dict(result))
            return

        # El worker escribe su propio error; stderr es el respaldo si murió antes.
        detail = (
            result.get("error")
            or stderr.strip()[-800:]
            or f"El proceso terminó con código {process.returncode}"
        )
        self._listener.failed(video_id, detail)

    def _worker(self) -> None:
        while True:
            video_id = self._queue.get()
            try:
                self._run(video_id)
            except Exception as exc:  # noqa: BLE001 - el hilo no debe morir nunca
                self._listener.failed(video_id, f"{type(exc).__name__}: {exc}")
            finally:
                self._queue.task_done()
