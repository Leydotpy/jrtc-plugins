from __future__ import annotations

from pathlib import Path

from stream_orchestrator_process import ProcessExecutor, ProcessSourceDriver

from .builder import FfmpegCommandBuilder
from .profiles import FfmpegProfile, default_profiles


def make_ffmpeg_driver(
    *,
    executor: ProcessExecutor,
    profiles: dict[str, FfmpegProfile] | None = None,
    executable: str = "ffmpeg",
    allowed_file_roots: tuple[Path, ...] = (),
    name: str = "ffmpeg",
) -> ProcessSourceDriver:
    return ProcessSourceDriver(
        name=name,
        executor=executor,
        builder=FfmpegCommandBuilder(
            profiles=profiles or default_profiles(),
            executable=executable,
            allowed_file_roots=allowed_file_roots,
        ),
    )
