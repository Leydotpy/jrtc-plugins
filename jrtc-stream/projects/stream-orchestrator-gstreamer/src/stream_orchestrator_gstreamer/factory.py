from __future__ import annotations

from pathlib import Path

from stream_orchestrator_process import ProcessExecutor, ProcessSourceDriver

from .builder import GstreamerCommandBuilder
from .profiles import GstreamerProfile, default_profiles


def make_gstreamer_driver(
    *,
    executor: ProcessExecutor,
    profiles: dict[str, GstreamerProfile] | None = None,
    executable: str = "gst-launch-1.0",
    allowed_file_roots: tuple[Path, ...] = (),
    name: str = "gstreamer",
) -> ProcessSourceDriver:
    return ProcessSourceDriver(
        name=name,
        executor=executor,
        builder=GstreamerCommandBuilder(
            profiles=profiles or default_profiles(),
            executable=executable,
            allowed_file_roots=allowed_file_roots,
        ),
    )
