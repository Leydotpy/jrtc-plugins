from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from stream_orchestrator import SourceContext, StreamDefinition

ProgressParser = Callable[[str], Mapping[str, str] | None]


@dataclass(frozen=True, slots=True)
class ProcessSpec:
    argv: tuple[str, ...]
    environment: Mapping[str, str] = field(default_factory=dict)
    cwd: str | None = None
    labels: Mapping[str, str] = field(default_factory=dict)
    progress_parser: ProgressParser | None = None
    stdout_tail_lines: int = 200
    stderr_tail_lines: int = 200

    def __post_init__(self) -> None:
        if not self.argv:
            raise ValueError("argv must not be empty")
        if any("\x00" in item for item in self.argv):
            raise ValueError("argv may not contain NUL bytes")
        if self.stdout_tail_lines < 0 or self.stderr_tail_lines < 0:
            raise ValueError("tail line limits must not be negative")


@dataclass(frozen=True, slots=True)
class ProcessRef:
    executor: str
    instance_id: str


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    running: bool
    exit_code: int | None
    started_at: datetime
    heartbeat_at: datetime | None
    progress: Mapping[str, str]
    stdout_tail: tuple[str, ...]
    stderr_tail: tuple[str, ...]


class ProcessExecutor(Protocol):
    name: str

    async def start(self, spec: ProcessSpec) -> ProcessRef: ...

    async def inspect(self, ref: ProcessRef) -> ProcessObservation: ...

    async def terminate(self, ref: ProcessRef, *, grace_seconds: float) -> None: ...


class CommandBuilder(Protocol):
    def build(
        self,
        context: SourceContext,
        definition: StreamDefinition,
    ) -> ProcessSpec: ...
