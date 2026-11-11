"""
Convención del log de eventos para los trabajos encolados.

Un tema terminado en `.completed` cierra el trabajo con éxito y uno en
`.failed` lo cierra con error; el resto son intermedios. La misma regla vive en
`web/domain/job.ts`: cambiarla afecta a los dos lados por igual.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4


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


SCRIPT_REQUESTED = "script.requested"
SCRIPT_COMPLETED = "script.completed"
SCRIPT_FAILED = "script.failed"
SCRIPT_TERMINAL = (SCRIPT_COMPLETED, SCRIPT_FAILED)

STORYBOARD_REQUESTED = "storyboard.requested"
STORYBOARD_COMPLETED = "storyboard.completed"
STORYBOARD_FAILED = "storyboard.failed"
STORYBOARD_TERMINAL = (STORYBOARD_COMPLETED, STORYBOARD_FAILED)

ILLUSTRATION_REQUESTED = "illustration.requested"
ILLUSTRATION_COMPLETED = "illustration.completed"
ILLUSTRATION_FAILED = "illustration.failed"
ILLUSTRATION_TERMINAL = (ILLUSTRATION_COMPLETED, ILLUSTRATION_FAILED)

REFERENCE_REQUESTED = "reference.requested"
REFERENCE_COMPLETED = "reference.completed"
REFERENCE_FAILED = "reference.failed"
REFERENCE_TERMINAL = (REFERENCE_COMPLETED, REFERENCE_FAILED)

Outcome = Literal["completed", "failed", "pending"]


def outcome_of(topic: str) -> Outcome:
    if topic.endswith(".completed"):
        return "completed"
    if topic.endswith(".failed"):
        return "failed"
    return "pending"


def new_job_key(prefix: str = "sc") -> str:
    return f"{prefix}-{uuid4().hex[:10]}"
