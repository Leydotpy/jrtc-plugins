"""Illustrative in-process composition for a small single-node application.

A production web deployment should normally move process supervision and
reconciliation to dedicated workers. Supply an already-created jrtc
session to ``build_stack``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from janus_stream_orchestrator import (
    JanusBackendSettings,
    JanusStreamingMountpointBackend,
)
from janus_streaming import StreamingRuntime, StreamingRuntimeSettings
from stream_orchestrator import (
    InMemoryEventBus,
    InMemoryLockManager,
    InMemoryStreamRepository,
    MediaKind,
    OrchestratorService,
    PipelineSpec,
    SourceDriverRegistry,
    SourceSpec,
    StreamController,
    StreamDefinition,
    SystemClock,
    TrackContract,
)
from stream_orchestrator_ffmpeg import make_ffmpeg_driver
from stream_orchestrator_process import LocalProcessExecutor


@dataclass(slots=True)
class LocalStack:
    runtime: StreamingRuntime
    executor: LocalProcessExecutor
    service: OrchestratorService

    async def close(self) -> None:
        await self.executor.close()
        await self.runtime.close()


async def build_stack(janus_session: Any) -> LocalStack:
    runtime = StreamingRuntime(
        janus_session,
        StreamingRuntimeSettings(
            admin_key=os.environ.get("JANUS_STREAMING_ADMIN_KEY"),
        ),
    )
    await runtime.start()

    executor = LocalProcessExecutor(allowed_executables={"ffmpeg"})
    ffmpeg = make_ffmpeg_driver(
        executor=executor,
        allowed_file_roots=(Path("/srv/media"),),
    )
    drivers = SourceDriverRegistry()
    drivers.register(ffmpeg)

    clock = SystemClock()
    repository = InMemoryStreamRepository(clock=clock)
    controller = StreamController(
        repository=repository,
        mountpoints=JanusStreamingMountpointBackend(
            runtime.admin,
            settings=JanusBackendSettings(rtp_host="janus.internal"),
        ),
        drivers=drivers,
        locks=InMemoryLockManager(),
        events=InMemoryEventBus(),
        clock=clock,
    )
    return LocalStack(
        runtime=runtime,
        executor=executor,
        service=OrchestratorService(
            repository=repository,
            controller=controller,
            clock=clock,
        ),
    )


def sample_definition() -> StreamDefinition:
    return StreamDefinition(
        name="Presentation",
        source=SourceSpec(kind="uri", locator="file:///srv/media/presentation.mp4"),
        pipeline=PipelineSpec(driver="ffmpeg", profile="h264-opus-low-latency"),
        tracks=(
            TrackContract(
                mid="audio",
                kind=MediaKind.AUDIO,
                codec="opus",
                payload_type=111,
                clock_rate=48_000,
                channels=2,
            ),
            TrackContract(
                mid="video",
                kind=MediaKind.VIDEO,
                codec="h264",
                payload_type=96,
                clock_rate=90_000,
                fmtp="profile-level-id=42e01f;packetization-mode=1",
            ),
        ),
    )
