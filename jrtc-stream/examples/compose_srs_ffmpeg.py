"""Compose SRS publisher readiness with an independently selected FFmpeg driver."""

from __future__ import annotations

from pathlib import Path

from stream_orchestrator import SourceDriverRegistry, SourceGateRegistry
from stream_orchestrator_ffmpeg import make_ffmpeg_driver
from stream_orchestrator_process import LocalProcessExecutor
from stream_orchestrator_srs import SrsClient, SrsPublisherGate


def build_source_plugins():
    executor = LocalProcessExecutor(allowed_executables={"ffmpeg"})
    drivers = SourceDriverRegistry()
    drivers.register(
        make_ffmpeg_driver(
            executor=executor,
            allowed_file_roots=(Path("/srv/media"),),
        )
    )

    srs = SrsClient(base_url="http://srs.internal:1985")
    gates = SourceGateRegistry()
    gates.register(SrsPublisherGate(srs))
    return executor, srs, drivers, gates
