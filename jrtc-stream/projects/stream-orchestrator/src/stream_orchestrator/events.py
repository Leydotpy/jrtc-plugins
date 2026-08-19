from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from .models import utc_now


@dataclass(frozen=True, slots=True)
class StreamEvent:
    kind: str
    stream_id: UUID
    generation: int
    data: Mapping[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=utc_now)


class InMemoryEventBus:
    """Bounded, process-local event bus suitable for tests and desktop apps.

    Slow subscribers lose the oldest event rather than applying unbounded
    backpressure to source reconciliation.
    """

    def __init__(self, *, queue_size: int = 128) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be at least 1")
        self._queue_size = queue_size
        self._subscribers: dict[UUID | None, set[asyncio.Queue[StreamEvent]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, event: StreamEvent) -> None:
        async with self._lock:
            queues = tuple(self._subscribers[event.stream_id] | self._subscribers[None])

        for queue in queues:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

    async def subscribe(self, stream_id: UUID | None = None) -> AsyncIterator[StreamEvent]:
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=self._queue_size)
        async with self._lock:
            self._subscribers[stream_id].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers[stream_id].discard(queue)
