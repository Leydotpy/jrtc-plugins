from __future__ import annotations

import asyncio
import os
import signal
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from .models import ProcessObservation, ProcessRef, ProcessSpec

_kill_process_group = cast(Callable[[int, int], None], getattr(os, "killpg", None))
_sigkill = cast(int, getattr(signal, "SIGKILL", signal.SIGTERM))


@dataclass(slots=True)
class _ManagedProcess:
    spec: ProcessSpec
    process: asyncio.subprocess.Process
    started_at: datetime
    stdout: deque[str]
    stderr: deque[str]
    progress: dict[str, str] = field(default_factory=dict)
    heartbeat_at: datetime | None = None
    readers: tuple[asyncio.Task[None], ...] = ()


class LocalProcessExecutor:
    """Owns subprocesses in the current Python process.

    Commands are always launched with `create_subprocess_exec`; shell parsing is
    deliberately unavailable. Optional executable allowlisting provides an
    additional defense when command builders are supplied by plugins.
    """

    name = "local-process"

    def __init__(
        self,
        *,
        allowed_executables: set[str] | None = None,
        base_environment: Mapping[str, str] | None = None,
    ) -> None:
        self._allowed = set(allowed_executables or ())
        self._base_environment = dict(base_environment or os.environ)
        self._processes: dict[str, _ManagedProcess] = {}
        self._lock = asyncio.Lock()

    async def start(self, spec: ProcessSpec) -> ProcessRef:
        executable = spec.argv[0]
        if self._allowed and not self._is_allowed_executable(executable):
            raise PermissionError(f"executable {executable!r} is not allowlisted")

        environment = dict(self._base_environment)
        environment.update(spec.environment)
        process = await asyncio.create_subprocess_exec(
            *spec.argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=spec.cwd,
            env=environment,
            start_new_session=os.name != "nt",
        )
        instance_id = str(uuid4())
        managed = _ManagedProcess(
            spec=spec,
            process=process,
            started_at=datetime.now(UTC),
            stdout=deque(maxlen=spec.stdout_tail_lines),
            stderr=deque(maxlen=spec.stderr_tail_lines),
        )
        stdout_task = asyncio.create_task(
            self._read_stream(managed, process.stdout, is_stdout=True),
            name=f"process-stdout-{instance_id}",
        )
        stderr_task = asyncio.create_task(
            self._read_stream(managed, process.stderr, is_stdout=False),
            name=f"process-stderr-{instance_id}",
        )
        managed.readers = (stdout_task, stderr_task)
        async with self._lock:
            self._processes[instance_id] = managed
        return ProcessRef(executor=self.name, instance_id=instance_id)

    async def inspect(self, ref: ProcessRef) -> ProcessObservation:
        managed = await self._get(ref)
        return ProcessObservation(
            running=managed.process.returncode is None,
            exit_code=managed.process.returncode,
            started_at=managed.started_at,
            heartbeat_at=managed.heartbeat_at,
            progress=dict(managed.progress),
            stdout_tail=tuple(managed.stdout),
            stderr_tail=tuple(managed.stderr),
        )

    async def terminate(self, ref: ProcessRef, *, grace_seconds: float) -> None:
        if grace_seconds < 0:
            raise ValueError("grace_seconds must not be negative")
        managed = await self._get(ref)
        process = managed.process
        if process.returncode is None:
            if os.name != "nt":
                try:
                    _kill_process_group(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            else:
                process.terminate()
            try:
                async with asyncio.timeout(grace_seconds):
                    await process.wait()
            except TimeoutError:
                if os.name != "nt":
                    try:
                        _kill_process_group(process.pid, _sigkill)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                await process.wait()

        for task in managed.readers:
            if not task.done():
                task.cancel()
        await asyncio.gather(*managed.readers, return_exceptions=True)
        async with self._lock:
            self._processes.pop(ref.instance_id, None)

    async def close(self, *, grace_seconds: float = 3.0) -> None:
        async with self._lock:
            refs = tuple(
                ProcessRef(executor=self.name, instance_id=instance_id)
                for instance_id in self._processes
            )
        await asyncio.gather(
            *(self.terminate(ref, grace_seconds=grace_seconds) for ref in refs),
            return_exceptions=True,
        )

    async def _get(self, ref: ProcessRef) -> _ManagedProcess:
        if ref.executor != self.name:
            raise ValueError(f"process belongs to executor {ref.executor!r}")
        async with self._lock:
            try:
                return self._processes[ref.instance_id]
            except KeyError as exc:
                raise LookupError(f"unknown process {ref.instance_id}") from exc

    async def _read_stream(
        self,
        managed: _ManagedProcess,
        stream: asyncio.StreamReader | None,
        *,
        is_stdout: bool,
    ) -> None:
        if stream is None:
            return
        target = managed.stdout if is_stdout else managed.stderr
        while True:
            line = await stream.readline()
            if not line:
                return
            text = line.decode("utf-8", errors="replace").rstrip("\r\n")
            target.append(text)
            managed.heartbeat_at = datetime.now(UTC)
            parser = managed.spec.progress_parser
            if parser is not None:
                parsed = parser(text)
                if parsed:
                    managed.progress.update(parsed)

    def _is_allowed_executable(self, executable: str) -> bool:
        """Apply exact-path matching to paths and basename matching to commands.

        A path such as ``/tmp/ffmpeg`` must not be accepted merely because the
        basename ``ffmpeg`` is allowlisted. Bare command names may be matched by
        basename because normal PATH resolution happens only after this check.
        """

        if executable in self._allowed:
            return True

        path = Path(executable)
        is_bare_command = path.name == executable and not path.is_absolute()
        return is_bare_command and path.name in self._allowed
