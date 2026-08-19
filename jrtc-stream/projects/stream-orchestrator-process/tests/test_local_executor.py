from __future__ import annotations

import sys

import pytest

from stream_orchestrator_process import LocalProcessExecutor, ProcessSpec


@pytest.mark.asyncio
async def test_executor_captures_bounded_output_and_progress():
    executor = LocalProcessExecutor(allowed_executables={sys.executable})

    def parser(line: str):
        if "=" not in line:
            return None
        key, value = line.split("=", 1)
        return {key: value}

    ref = await executor.start(
        ProcessSpec(
            argv=(
                sys.executable,
                "-c",
                "import time; print('frame=10', flush=True); time.sleep(0.2)",
            ),
            progress_parser=parser,
        )
    )
    asyncio = __import__("asyncio")
    observation = await executor.inspect(ref)
    for _ in range(120):
        if observation.progress.get("frame") == "10":
            break
        await asyncio.sleep(0.05)
        observation = await executor.inspect(ref)
    assert observation.progress.get("frame") == "10"
    await executor.terminate(ref, grace_seconds=1.0)


@pytest.mark.asyncio
async def test_executable_allowlist_rejects_lookalike_path() -> None:
    executor = LocalProcessExecutor(allowed_executables={"ffmpeg"})

    with pytest.raises(PermissionError, match="not allowlisted"):
        await executor.start(ProcessSpec(argv=("/tmp/ffmpeg", "-version")))
