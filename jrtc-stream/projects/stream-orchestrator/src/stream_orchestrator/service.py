from __future__ import annotations

import asyncio
from dataclasses import replace
from uuid import UUID

from .controller import StreamController
from .models import (
    DesiredState,
    MediaState,
    OperationalState,
    ProducerState,
    StreamDefinition,
    StreamRecord,
    StreamStatus,
)
from .ports import Clock, StreamRepository


class OrchestratorService:
    """Intent-oriented API used by Django, Qt, CLIs, and worker services."""

    def __init__(
        self,
        *,
        repository: StreamRepository,
        controller: StreamController,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._controller = controller
        self._clock = clock

    async def define(self, definition: StreamDefinition) -> StreamRecord:
        return await self._repository.create(
            StreamRecord(
                definition=definition,
                status=StreamStatus(stream_id=definition.id),
            )
        )

    async def get(self, stream_id: UUID) -> StreamRecord:
        return await self._repository.get(stream_id)

    async def list(self) -> tuple[StreamRecord, ...]:
        return await self._repository.list()

    async def request_start(
        self,
        stream_id: UUID,
        *,
        expected_revision: int | None = None,
    ) -> StreamRecord:
        record = await self._repository.get(stream_id)
        expected = record.revision if expected_revision is None else expected_revision
        terminal = record.status.operational in {
            OperationalState.FAILED,
            OperationalState.STOPPED,
        }
        status = replace(
            record.status,
            desired=DesiredState.RUNNING,
            producer=(ProducerState.NONE if terminal else record.status.producer),
            media=(MediaState.UNKNOWN if terminal else record.status.media),
            operational=(
                OperationalState.READY
                if record.status.operational is OperationalState.READY
                else OperationalState.PENDING
            ),
            restart_count=(0 if terminal else record.status.restart_count),
            next_retry_at=None,
            reason_code=None,
            reason_message=None,
        )
        return await self._repository.save(
            replace(record, status=status),
            expected_revision=expected,
        )

    async def request_stop(
        self,
        stream_id: UUID,
        *,
        expected_revision: int | None = None,
    ) -> StreamRecord:
        record = await self._repository.get(stream_id)
        expected = record.revision if expected_revision is None else expected_revision
        status = replace(
            record.status,
            desired=DesiredState.STOPPED,
            operational=OperationalState.PENDING,
        )
        return await self._repository.save(
            replace(record, status=status),
            expected_revision=expected,
        )

    async def request_delete(
        self,
        stream_id: UUID,
        *,
        expected_revision: int | None = None,
    ) -> StreamRecord:
        record = await self._repository.get(stream_id)
        expected = record.revision if expected_revision is None else expected_revision
        status = replace(
            record.status,
            desired=DesiredState.DELETED,
            operational=OperationalState.PENDING,
        )
        return await self._repository.save(
            replace(record, status=status),
            expected_revision=expected,
        )

    async def purge_deleted(self, stream_id: UUID) -> None:
        record = await self._repository.get(stream_id)
        if record.status.desired is not DesiredState.DELETED:
            raise ValueError("stream must be marked deleted before purge")
        if record.status.operational is not OperationalState.STOPPED:
            raise ValueError("stream must be fully stopped before purge")
        await self._repository.delete(stream_id, expected_revision=record.revision)

    async def reconcile(self, stream_id: UUID) -> StreamRecord:
        return await self._controller.reconcile(stream_id)

    async def start_now(self, stream_id: UUID, *, deadline_seconds: float = 30.0) -> StreamRecord:
        await self.request_start(stream_id)
        async with asyncio.timeout(deadline_seconds):
            while True:
                record = await self.reconcile(stream_id)
                if record.status.operational is OperationalState.READY:
                    return record
                if record.status.operational is OperationalState.FAILED:
                    return record
                await self._sleep(0.25)

    async def stop_now(self, stream_id: UUID, *, deadline_seconds: float = 30.0) -> StreamRecord:
        await self.request_stop(stream_id)
        async with asyncio.timeout(deadline_seconds):
            while True:
                record = await self.reconcile(stream_id)
                if record.status.operational is OperationalState.STOPPED:
                    return record
                await self._sleep(0.25)

    async def _sleep(self, seconds: float) -> None:
        if self._clock is None:
            await asyncio.sleep(seconds)
        else:
            await self._clock.sleep(seconds)
