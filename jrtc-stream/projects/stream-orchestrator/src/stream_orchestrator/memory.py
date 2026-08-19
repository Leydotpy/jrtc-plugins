from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID

from .errors import ConcurrencyConflict, StreamAlreadyExists, StreamNotFound
from .models import StreamRecord
from .ports import Clock


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class InMemoryStreamRepository:
    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or SystemClock()
        self._records: dict[UUID, StreamRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, record: StreamRecord) -> StreamRecord:
        async with self._lock:
            if record.id in self._records:
                raise StreamAlreadyExists(record.id)
            now = self._clock.now()
            stored = replace(record, revision=0, created_at=now, updated_at=now)
            self._records[stored.id] = stored
            return stored

    async def get(self, stream_id: UUID) -> StreamRecord:
        async with self._lock:
            try:
                return self._records[stream_id]
            except KeyError as exc:
                raise StreamNotFound(stream_id) from exc

    async def list(self) -> tuple[StreamRecord, ...]:
        async with self._lock:
            return tuple(sorted(self._records.values(), key=lambda item: str(item.id)))

    async def save(self, record: StreamRecord, *, expected_revision: int) -> StreamRecord:
        async with self._lock:
            try:
                current = self._records[record.id]
            except KeyError as exc:
                raise StreamNotFound(record.id) from exc
            if current.revision != expected_revision:
                raise ConcurrencyConflict(record.id, expected_revision, current.revision)
            stored = replace(
                record,
                revision=expected_revision + 1,
                created_at=current.created_at,
                updated_at=self._clock.now(),
            )
            self._records[record.id] = stored
            return stored

    async def delete(self, stream_id: UUID, *, expected_revision: int) -> None:
        async with self._lock:
            try:
                current = self._records[stream_id]
            except KeyError as exc:
                raise StreamNotFound(stream_id) from exc
            if current.revision != expected_revision:
                raise ConcurrencyConflict(stream_id, expected_revision, current.revision)
            del self._records[stream_id]


@dataclass(frozen=True, slots=True)
class InMemoryLockLease:
    key: str
    fencing_token: int


class InMemoryLockManager:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._tokens: dict[str, int] = defaultdict(int)
        self._guard = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, key: str) -> AsyncIterator[InMemoryLockLease]:
        async with self._guard:
            lock = self._locks[key]
        async with lock:
            async with self._guard:
                self._tokens[key] += 1
                token = self._tokens[key]
            yield InMemoryLockLease(key=key, fencing_token=token)
