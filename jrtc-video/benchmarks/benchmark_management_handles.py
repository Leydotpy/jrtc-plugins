"""Compare temporary and persistent VideoRoom management-handle request counts."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from typing import Any

from jrtc_video import VideoRoomPlugin, VideoRoomService


class _Registry:
    def __init__(self) -> None:
        self.handles: dict[int, VideoRoomPlugin] = {}

    def register(self, handle_id: int, plugin: VideoRoomPlugin) -> None:
        self.handles[handle_id] = plugin

    def get(self, handle_id: int) -> VideoRoomPlugin | None:
        return self.handles.get(handle_id)

    def unregister(self, handle_id: int) -> None:
        self.handles.pop(handle_id, None)


class _BenchmarkSession:
    id = 700
    ready = True
    generation = 1

    def __init__(self, latency_seconds: float) -> None:
        self.latency_seconds = latency_seconds
        self.plugins = _Registry()
        self.attach_count = 0
        self.command_count = 0
        self.detach_count = 0
        self._next_handle = 10

    async def _latency(self) -> None:
        if self.latency_seconds:
            await asyncio.sleep(self.latency_seconds)

    async def attach(self, _name: str, *, opaque_id: str | None = None) -> int:
        del opaque_id
        await self._latency()
        self.attach_count += 1
        self._next_handle += 1
        return self._next_handle

    async def detach(self, handle_id: int) -> int:
        await self._latency()
        self.detach_count += 1
        self.plugins.unregister(handle_id)
        return handle_id

    async def send(self, message: Any, **_options: Any) -> dict[str, Any]:
        await self._latency()
        self.command_count += 1
        room = message.body.get("room", 1234)
        return {
            "janus": "event",
            "transaction": message.transaction,
            "plugindata": {
                "plugin": "janus.plugin.videoroom",
                "data": {
                    "videoroom": "participants",
                    "room": room,
                    "participants": [],
                },
            },
        }


def _percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[index]


async def _temporary(commands: int, latency: float) -> tuple[_BenchmarkSession, list[float], float]:
    session = _BenchmarkSession(latency)
    durations: list[float] = []
    cpu_started = time.process_time()
    for _ in range(commands):
        started = time.perf_counter()
        async with VideoRoomPlugin(session=session) as plugin:
            await plugin.list_participants(1234)
        durations.append(time.perf_counter() - started)
    return session, durations, time.process_time() - cpu_started


async def _persistent(
    commands: int, latency: float
) -> tuple[_BenchmarkSession, list[float], float]:
    session = _BenchmarkSession(latency)
    service = VideoRoomService(session)
    durations: list[float] = []
    cpu_started = time.process_time()
    for _ in range(commands):
        started = time.perf_counter()
        await service.list_participants(1234)
        durations.append(time.perf_counter() - started)
    await service.aclose()
    return session, durations, time.process_time() - cpu_started


def _report(session: _BenchmarkSession, durations: list[float], cpu: float) -> dict[str, Any]:
    return {
        "attach_count": session.attach_count,
        "command_count": session.command_count,
        "detach_count": session.detach_count,
        "handles_after_shutdown": len(session.plugins.handles),
        "latency_ms_p50": statistics.median(durations) * 1000,
        "latency_ms_p95": _percentile(durations, 0.95) * 1000,
        "cpu_ms": cpu * 1000,
    }


async def _main(commands: int, latency_ms: float) -> None:
    if commands < 1:
        raise ValueError("--commands must be positive")
    if latency_ms < 0:
        raise ValueError("--latency-ms cannot be negative")
    latency = latency_ms / 1000
    temporary = await _temporary(commands, latency)
    persistent = await _persistent(commands, latency)
    report = {
        "commands": commands,
        "simulated_transaction_latency_ms": latency_ms,
        "temporary_handle": _report(*temporary),
        "persistent_handle": _report(*persistent),
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    persistent_report = report["persistent_handle"]
    if (
        persistent_report["attach_count"] != 1
        or persistent_report["command_count"] != commands
        or persistent_report["detach_count"] != 1
        or persistent_report["handles_after_shutdown"] != 0
    ):
        raise RuntimeError("persistent management-handle invariants failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--commands", type=int, default=100)
    parser.add_argument("--latency-ms", type=float, default=0.1)
    options = parser.parse_args()
    asyncio.run(_main(options.commands, options.latency_ms))
