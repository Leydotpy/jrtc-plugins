from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from stream_orchestrator import (
    MountpointObservation,
    MountpointRef,
    PreparedSource,
    ProducerState,
    RtpTarget,
    SourceObservation,
    SourceRuntimeRef,
    StreamDefinition,
    TrackObservation,
)


class FakeClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    async def sleep(self, seconds: float) -> None:
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)

    def advance_to(self, moment: datetime) -> None:
        if moment > self._now:
            self._now = moment


class FakeMountpoints:
    name = "fake"

    def __init__(self) -> None:
        self.created = 0
        self.enabled = False
        self.exists = True
        self.viewer_count = 0
        self.flowing = False
        self.destroyed_instances: list[str] = []

    @property
    def destroyed(self) -> bool:
        return bool(self.destroyed_instances)

    async def create(
        self,
        definition: StreamDefinition,
        *,
        generation: int,
    ) -> MountpointRef:
        self.created += 1
        self.exists = True
        self.enabled = False
        base_port = 5_000 + generation * 100
        targets = tuple(
            RtpTarget(
                mid=track.mid,
                kind=track.kind,
                host="127.0.0.1",
                rtp_port=base_port + index * 2,
                rtcp_port=base_port + index * 2 + 1,
                payload_type=track.payload_type,
                codec=track.codec,
                fmtp=track.fmtp,
            )
            for index, track in enumerate(definition.tracks)
        )
        return MountpointRef(
            backend=self.name,
            instance_id=f"mp-{generation}",
            generation=generation,
            targets=targets,
        )

    async def inspect(self, ref: MountpointRef) -> MountpointObservation:
        return MountpointObservation(
            exists=self.exists,
            enabled=self.enabled,
            viewer_count=self.viewer_count,
            tracks=tuple(
                TrackObservation(
                    mid=target.mid,
                    flowing=self.flowing,
                    packet_age_ms=50 if self.flowing else None,
                )
                for target in ref.targets
            ),
        )

    async def enable(self, ref: MountpointRef) -> None:
        self.enabled = True

    async def disable(self, ref: MountpointRef) -> None:
        self.enabled = False

    async def kick_all(self, ref: MountpointRef) -> None:
        self.viewer_count = 0

    async def destroy(self, ref: MountpointRef) -> None:
        self.destroyed_instances.append(ref.instance_id)
        self.exists = False
        self.enabled = False


class FakeDriver:
    name = "fake-driver"

    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.state = ProducerState.RUNNING
        self.healthy = True
        self.reason: str | None = None
        self.start_error: Exception | None = None
        self.started_targets: list[tuple[int, ...]] = []

    async def prepare(self, context: Any, definition: StreamDefinition) -> PreparedSource:
        return PreparedSource(driver=self.name, payload={"targets": context.targets})

    async def start(self, prepared: PreparedSource, *, generation: int) -> SourceRuntimeRef:
        if self.start_error is not None:
            raise self.start_error
        self.started += 1
        targets = prepared.payload["targets"]
        self.started_targets.append(tuple(target.rtp_port for target in targets))
        return SourceRuntimeRef(
            driver=self.name,
            instance_id=f"source-{generation}-{self.started}",
            generation=generation,
        )

    async def inspect(self, ref: SourceRuntimeRef) -> SourceObservation:
        return SourceObservation(
            state=self.state,
            healthy=self.healthy,
            reason=self.reason,
        )

    async def stop(self, ref: SourceRuntimeRef, *, deadline_seconds: float) -> None:
        self.stopped += 1

    async def cleanup(self, prepared: PreparedSource) -> None:
        return None
