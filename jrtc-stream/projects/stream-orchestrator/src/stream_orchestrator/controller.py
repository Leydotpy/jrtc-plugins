from __future__ import annotations

import asyncio
import logging
import random
from contextlib import suppress
from dataclasses import replace
from datetime import timedelta
from uuid import UUID

from .events import StreamEvent
from .models import (
    DesiredState,
    MediaState,
    MountpointState,
    OperationalState,
    PreparedSource,
    ProducerState,
    SourceContext,
    SourceObservation,
    StreamRecord,
    StreamStatus,
)
from .ports import Clock, EventPublisher, LockManager, MountpointBackend, StreamRepository
from .registry import SourceDriverRegistry, SourceGateRegistry

logger = logging.getLogger(__name__)


class StreamController:
    """Idempotent reconciler for one logical stream.

    The controller deliberately performs small, repeatable steps. Persistent
    adapters can recover after a process crash by inspecting stored references
    and invoking `reconcile` again.
    """

    def __init__(
        self,
        *,
        repository: StreamRepository,
        mountpoints: MountpointBackend,
        drivers: SourceDriverRegistry,
        locks: LockManager,
        events: EventPublisher,
        clock: Clock,
        gates: SourceGateRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._mountpoints = mountpoints
        self._drivers = drivers
        self._gates = gates or SourceGateRegistry()
        self._locks = locks
        self._events = events
        self._clock = clock

    async def reconcile(self, stream_id: UUID) -> StreamRecord:
        async with self._locks.acquire(f"stream:{stream_id}"):
            record = await self._repository.get(stream_id)
            try:
                if record.status.desired is DesiredState.RUNNING:
                    return await self._ensure_running(record)
                return await self._ensure_stopped(record)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception(
                    "stream reconciliation failed",
                    extra={"stream_id": str(stream_id)},
                )
                failed = await self._mark_failure(record, exc)
                await self._emit(failed, "stream.reconcile_failed", error=str(exc))
                return failed

    async def _ensure_running(self, record: StreamRecord) -> StreamRecord:
        if (
            record.status.source_ref is None
            and record.status.producer in {ProducerState.FAILED, ProducerState.STOPPED}
            and record.status.operational in {OperationalState.FAILED, OperationalState.STOPPED}
        ):
            # Terminal states are latched until a new explicit start request
            # resets them. This prevents an exhausted restart policy or a
            # clean end-of-stream from immediately creating another process.
            return record

        retry_at = record.status.next_retry_at
        if (
            record.status.producer is ProducerState.BACKING_OFF
            and retry_at is not None
            and self._clock.now() < retry_at
        ):
            return record

        if record.status.producer is ProducerState.BACKING_OFF and retry_at is not None:
            status = replace(
                record.status,
                producer=ProducerState.NONE,
                next_retry_at=None,
                reason_code=None,
                reason_message=None,
                last_transition_at=self._clock.now(),
            )
            record = await self._save_status(record, status)

        record = await self._ensure_mountpoint(record)

        gate = self._gates.get_optional(record.definition.source.kind)
        if gate is not None:
            gate_observation = await gate.inspect(record.definition)
            if not gate_observation.ready:
                waiting = replace(
                    record.status,
                    producer=gate_observation.state,
                    media=MediaState.UNKNOWN,
                    operational=OperationalState.PENDING,
                    reason_code="source_not_ready",
                    reason_message=gate_observation.reason,
                    last_transition_at=self._clock.now(),
                )
                return await self._save_status(record, waiting)

        record = await self._ensure_source(record)
        source_ref = record.status.source_ref
        mountpoint_ref = record.status.mountpoint_ref
        if source_ref is None or mountpoint_ref is None:
            return record

        driver = self._drivers.get(record.definition.pipeline.driver)
        source = await driver.inspect(source_ref)
        mountpoint = await self._mountpoints.inspect(mountpoint_ref)

        if not mountpoint.exists:
            # A managed producer targets the concrete ports of one mountpoint
            # generation. If that mountpoint disappears, the producer cannot
            # safely be reused with a replacement generation.
            with suppress(Exception):
                await driver.stop(source_ref, deadline_seconds=5.0)
            status = replace(
                record.status,
                mountpoint=MountpointState.ABSENT,
                mountpoint_ref=None,
                source_ref=None,
                producer=ProducerState.NONE,
                media=MediaState.UNKNOWN,
                operational=OperationalState.PENDING,
                reason_code="mountpoint_missing",
                reason_message="mountpoint disappeared; source will be retargeted",
                last_transition_at=self._clock.now(),
            )
            return await self._save_status(record, status)

        if source.state is ProducerState.FAILED or not source.healthy:
            return await self._handle_source_failure(record, source)

        required = {track.mid for track in record.definition.tracks if track.required}
        stale_after_ms = int(record.definition.lifecycle.media_stale_after_seconds * 1000)
        flowing = {
            track.mid
            for track in mountpoint.tracks
            if track.flowing
            and track.packet_age_ms is not None
            and track.packet_age_ms <= stale_after_ms
        }
        media_ready = required <= flowing if required else bool(flowing)

        if media_ready:
            if not mountpoint.enabled:
                await self._mountpoints.enable(mountpoint_ref)
            status = replace(
                record.status,
                mountpoint=MountpointState.ENABLED,
                producer=ProducerState.RUNNING,
                media=MediaState.FLOWING,
                operational=OperationalState.READY,
                tracks=mountpoint.tracks,
                reason_code=None,
                reason_message=None,
                last_transition_at=self._clock.now(),
                last_heartbeat_at=source.progress_at or self._clock.now(),
                next_retry_at=None,
            )
            saved = await self._save_status(record, status)
            if record.status.operational is not OperationalState.READY:
                await self._emit(saved, "stream.ready")
            return saved

        if mountpoint.enabled and record.definition.lifecycle.disable_when_stale:
            await self._mountpoints.disable(mountpoint_ref)

        operational = (
            OperationalState.DEGRADED
            if record.status.operational is OperationalState.READY
            else OperationalState.PENDING
        )
        status = replace(
            record.status,
            mountpoint=MountpointState.DISABLED,
            producer=source.state,
            media=MediaState.STALE if mountpoint.tracks else MediaState.WARMING,
            operational=operational,
            tracks=mountpoint.tracks,
            reason_code="media_not_flowing",
            reason_message=f"required tracks not fresh: {sorted(required - flowing)}",
            last_transition_at=self._clock.now(),
            last_heartbeat_at=source.progress_at,
        )
        saved = await self._save_status(record, status)
        if operational is OperationalState.DEGRADED:
            await self._emit(saved, "stream.degraded", reason=status.reason_message)
        return saved

    async def _ensure_mountpoint(self, record: StreamRecord) -> StreamRecord:
        if record.status.mountpoint_ref is not None:
            return record

        generation = record.status.generation + 1
        creating = replace(
            record.status,
            generation=generation,
            mountpoint=MountpointState.CREATING,
            producer=ProducerState.PREPARING,
            media=MediaState.UNKNOWN,
            operational=OperationalState.PENDING,
            reason_code=None,
            reason_message=None,
            last_transition_at=self._clock.now(),
        )
        record = await self._save_status(record, creating)

        try:
            ref = await self._mountpoints.create(record.definition, generation=generation)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return await self._handle_source_failure(
                record,
                SourceObservation(
                    state=ProducerState.FAILED,
                    healthy=False,
                    reason=f"mountpoint creation failed: {exc}",
                ),
            )
        status = replace(
            record.status,
            mountpoint_ref=ref,
            mountpoint=MountpointState.DISABLED,
            last_transition_at=self._clock.now(),
        )
        saved = await self._save_status(record, status)
        await self._emit(saved, "mountpoint.created", mountpoint_id=ref.instance_id)
        return saved

    async def _ensure_source(self, record: StreamRecord) -> StreamRecord:
        if record.status.source_ref is not None:
            return record
        mountpoint_ref = record.status.mountpoint_ref
        if mountpoint_ref is None:
            return record

        driver = self._drivers.get(record.definition.pipeline.driver)
        context = SourceContext(
            stream_id=record.id,
            generation=record.status.generation,
            targets=mountpoint_ref.targets,
            startup_timeout_seconds=record.definition.lifecycle.startup_timeout_seconds,
        )
        status = replace(
            record.status,
            producer=ProducerState.PREPARING,
            operational=OperationalState.PENDING,
            last_transition_at=self._clock.now(),
        )
        record = await self._save_status(record, status)

        prepared: PreparedSource | None = None
        try:
            prepared = await driver.prepare(context, record.definition)
            status = replace(
                record.status,
                producer=ProducerState.STARTING,
                last_transition_at=self._clock.now(),
            )
            record = await self._save_status(record, status)
            ref = await driver.start(prepared, generation=record.status.generation)
        except asyncio.CancelledError:
            if prepared is not None:
                with suppress(Exception):
                    await asyncio.shield(driver.cleanup(prepared))
            raise
        except Exception as exc:
            if prepared is not None:
                with suppress(Exception):
                    await asyncio.shield(driver.cleanup(prepared))
            return await self._handle_source_failure(
                record,
                SourceObservation(
                    state=ProducerState.FAILED,
                    healthy=False,
                    reason=f"source start failed: {exc}",
                ),
            )

        status = replace(
            record.status,
            source_ref=ref,
            producer=ProducerState.STARTING,
            media=MediaState.WARMING,
            last_transition_at=self._clock.now(),
        )
        saved = await self._save_status(record, status)
        await self._emit(saved, "source.started", source_instance_id=ref.instance_id)
        return saved

    async def _handle_source_failure(
        self,
        record: StreamRecord,
        observation: SourceObservation,
    ) -> StreamRecord:
        ref = record.status.source_ref
        policy = record.definition.lifecycle.restart
        next_count = record.status.restart_count + 1
        attempts_exhausted = (
            policy.maximum_attempts is not None and next_count > policy.maximum_attempts
        )
        is_failure = observation.state is ProducerState.FAILED
        should_restart = (
            policy.mode == "always" or (policy.mode == "on-failure" and is_failure)
        ) and not attempts_exhausted

        driver = self._drivers.get(record.definition.pipeline.driver)
        if ref is not None:
            with suppress(Exception):
                await driver.stop(ref, deadline_seconds=5.0)

        mountpoint_ref = record.status.mountpoint_ref
        if mountpoint_ref is not None:
            with suppress(Exception):
                await self._mountpoints.disable(mountpoint_ref)

        if not should_restart:
            terminal_producer = ProducerState.FAILED if is_failure else ProducerState.STOPPED
            terminal_operational = (
                OperationalState.FAILED if is_failure else OperationalState.STOPPED
            )
            reason_code = "source_failed" if is_failure else "source_ended"
            reason_message = observation.reason or (
                "source failed" if is_failure else "source ended normally"
            )
            status = replace(
                record.status,
                source_ref=None,
                producer=terminal_producer,
                media=MediaState.ENDED,
                operational=terminal_operational,
                restart_count=next_count if is_failure else record.status.restart_count,
                next_retry_at=None,
                reason_code=reason_code,
                reason_message=reason_message,
                last_transition_at=self._clock.now(),
            )
            saved = await self._save_status(record, status)
            event = "source.failed" if is_failure else "source.ended"
            await self._emit(saved, event, reason=status.reason_message)
            return saved

        base = min(
            policy.maximum_delay_seconds,
            policy.initial_delay_seconds * (2 ** max(0, next_count - 1)),
        )
        delay = base * random.uniform(0.8, 1.2)
        status = replace(
            record.status,
            source_ref=None,
            producer=ProducerState.BACKING_OFF,
            media=MediaState.ENDED,
            operational=OperationalState.DEGRADED,
            restart_count=next_count,
            next_retry_at=self._clock.now() + timedelta(seconds=delay),
            reason_code="source_restarting",
            reason_message=observation.reason or "source failed; restart scheduled",
            last_transition_at=self._clock.now(),
        )
        saved = await self._save_status(record, status)
        await self._emit(saved, "source.restart_scheduled", delay_seconds=delay)
        return saved

    async def _ensure_stopped(self, record: StreamRecord) -> StreamRecord:
        status = record.status
        mountpoint_ref = status.mountpoint_ref
        source_ref = status.source_ref

        if mountpoint_ref is not None and status.mountpoint is MountpointState.ENABLED:
            await self._mountpoints.disable(mountpoint_ref)
            status = replace(
                status,
                mountpoint=MountpointState.DISABLED,
                operational=OperationalState.PENDING,
                last_transition_at=self._clock.now(),
            )
            record = await self._save_status(record, status)

        if source_ref is not None:
            driver = self._drivers.get(record.definition.pipeline.driver)
            status = replace(
                record.status,
                producer=ProducerState.STOPPING,
                last_transition_at=self._clock.now(),
            )
            record = await self._save_status(record, status)
            await driver.stop(source_ref, deadline_seconds=5.0)
            status = replace(
                record.status,
                source_ref=None,
                producer=ProducerState.STOPPED,
                media=MediaState.ENDED,
                last_transition_at=self._clock.now(),
            )
            record = await self._save_status(record, status)

        mountpoint_ref = record.status.mountpoint_ref
        if mountpoint_ref is not None and record.definition.lifecycle.destroy_when_stopped:
            status = replace(
                record.status,
                mountpoint=MountpointState.DESTROYING,
                last_transition_at=self._clock.now(),
            )
            record = await self._save_status(record, status)
            observation = await self._mountpoints.inspect(mountpoint_ref)
            if observation.exists and observation.viewer_count > 0:
                await self._mountpoints.kick_all(mountpoint_ref)
            await self._mountpoints.destroy(mountpoint_ref)
            status = replace(
                record.status,
                mountpoint_ref=None,
                mountpoint=MountpointState.ABSENT,
                last_transition_at=self._clock.now(),
            )
            record = await self._save_status(record, status)

        final = replace(
            record.status,
            producer=ProducerState.STOPPED,
            media=MediaState.ENDED,
            operational=OperationalState.STOPPED,
            reason_code=None,
            reason_message=None,
            next_retry_at=None,
            last_transition_at=self._clock.now(),
        )
        if final == record.status:
            return record
        saved = await self._save_status(record, final)
        await self._emit(saved, "stream.stopped")
        return saved

    async def _mark_failure(self, record: StreamRecord, exc: Exception) -> StreamRecord:
        latest = await self._repository.get(record.id)
        status = replace(
            latest.status,
            operational=OperationalState.FAILED,
            reason_code=exc.__class__.__name__,
            reason_message=str(exc),
            last_transition_at=self._clock.now(),
        )
        return await self._save_status(latest, status)

    async def _save_status(self, record: StreamRecord, status: StreamStatus) -> StreamRecord:
        return await self._repository.save(
            replace(record, status=status),
            expected_revision=record.revision,
        )

    async def _emit(self, record: StreamRecord, kind: str, **data: object) -> None:
        await self._events.publish(
            StreamEvent(
                kind=kind,
                stream_id=record.id,
                generation=record.status.generation,
                data=data,
            )
        )
