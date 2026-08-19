from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from .events import StreamEvent
from .models import (
    GateObservation,
    MountpointObservation,
    MountpointRef,
    PreparedSource,
    SourceContext,
    SourceObservation,
    SourceRuntimeRef,
    StreamDefinition,
    StreamRecord,
)


class Clock(Protocol):
    def now(self) -> datetime: ...

    async def sleep(self, seconds: float) -> None: ...


class StreamRepository(Protocol):
    async def create(self, record: StreamRecord) -> StreamRecord: ...

    async def get(self, stream_id: UUID) -> StreamRecord: ...

    async def list(self) -> tuple[StreamRecord, ...]: ...

    async def save(self, record: StreamRecord, *, expected_revision: int) -> StreamRecord: ...

    async def delete(self, stream_id: UUID, *, expected_revision: int) -> None: ...


class MountpointBackend(Protocol):
    name: str

    async def create(self, definition: StreamDefinition, *, generation: int) -> MountpointRef: ...

    async def inspect(self, ref: MountpointRef) -> MountpointObservation: ...

    async def enable(self, ref: MountpointRef) -> None: ...

    async def disable(self, ref: MountpointRef) -> None: ...

    async def kick_all(self, ref: MountpointRef) -> None: ...

    async def destroy(self, ref: MountpointRef) -> None: ...


class SourceDriver(Protocol):
    name: str

    async def prepare(
        self,
        context: SourceContext,
        definition: StreamDefinition,
    ) -> PreparedSource: ...

    async def start(self, prepared: PreparedSource, *, generation: int) -> SourceRuntimeRef: ...

    async def inspect(self, ref: SourceRuntimeRef) -> SourceObservation: ...

    async def stop(self, ref: SourceRuntimeRef, *, deadline_seconds: float) -> None: ...

    async def cleanup(self, prepared: PreparedSource) -> None: ...


class SourceGate(Protocol):
    kind: str

    async def inspect(self, definition: StreamDefinition) -> GateObservation: ...


class EventPublisher(Protocol):
    async def publish(self, event: StreamEvent) -> None: ...


class EventSubscriber(Protocol):
    async def subscribe(self, stream_id: UUID | None = None) -> AsyncIterator[StreamEvent]: ...


class LockLease(Protocol):
    key: str
    fencing_token: int


class LockManager(Protocol):
    def acquire(self, key: str) -> AbstractAsyncContextManager[LockLease]: ...


class StreamIdSource(Protocol):
    async def pending(self) -> Iterable[UUID]: ...
