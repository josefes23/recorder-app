"""Consumidor de un grupo sobre el log de eventos, con entrega al menos una vez."""

from __future__ import annotations

from collections.abc import Callable

from app.application.ports import EventLog
from app.domain.events import Event

# Cada cuánto despierta el consumidor si no hay nada que hacer. No es sondeo:
# `wait_for` se despierta sola al publicarse; esto solo evita esperas eternas.
IDLE_TIMEOUT = 30.0


class EventConsumer:
    def __init__(
        self,
        log: EventLog,
        group: str,
        topics: tuple[str, ...],
        handler: Callable[[Event], None],
        idle_timeout: float = IDLE_TIMEOUT,
    ) -> None:
        self._log = log
        self._group = group
        self._topics = topics
        self._handler = handler
        self._idle_timeout = idle_timeout

    def run_once(self, offset: int) -> int:
        """Procesa un lote y devuelve el offset por el que va."""
        for event in self._log.wait_for(offset, self._idle_timeout, topics=self._topics):
            self._handler(event)
            # Se confirma después de trabajar: si el proceso muere en medio, el
            # encargo se vuelve a entregar en lugar de perderse. El handler
            # tiene que ser idempotente por eso mismo.
            offset = event.offset
            self._log.commit(self._group, offset)
        return offset

    def run_forever(self) -> None:
        offset = self._log.committed_offset(self._group)
        while True:
            offset = self.run_once(offset)
