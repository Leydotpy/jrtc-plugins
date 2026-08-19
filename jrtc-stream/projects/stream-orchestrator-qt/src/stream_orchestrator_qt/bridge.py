from __future__ import annotations

import concurrent.futures
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

from stream_orchestrator import OrchestratorService, StreamRecord

from .runner import AsyncioLoopThread

SuccessCallback = Callable[[StreamRecord], None]
ErrorCallback = Callable[[BaseException], None]


class CallbackOrchestratorBridge:
    """Framework-neutral callbacks over the async application service."""

    def __init__(
        self,
        service: OrchestratorService,
        *,
        runner: AsyncioLoopThread | None = None,
    ) -> None:
        self._service = service
        self._runner = runner or AsyncioLoopThread()

    @property
    def runner(self) -> AsyncioLoopThread:
        return self._runner

    def start_stream(
        self,
        stream_id: UUID,
        *,
        deadline_seconds: float = 30.0,
        on_success: SuccessCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> concurrent.futures.Future[StreamRecord]:
        return self._submit(
            self._service.start_now(stream_id, deadline_seconds=deadline_seconds),
            on_success=on_success,
            on_error=on_error,
        )

    def stop_stream(
        self,
        stream_id: UUID,
        *,
        deadline_seconds: float = 30.0,
        on_success: SuccessCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> concurrent.futures.Future[StreamRecord]:
        return self._submit(
            self._service.stop_now(stream_id, deadline_seconds=deadline_seconds),
            on_success=on_success,
            on_error=on_error,
        )

    def refresh(
        self,
        stream_id: UUID,
        *,
        on_success: SuccessCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> concurrent.futures.Future[StreamRecord]:
        return self._submit(
            self._service.get(stream_id),
            on_success=on_success,
            on_error=on_error,
        )

    def close(self) -> None:
        self._runner.stop()

    def _submit(
        self,
        coroutine: Coroutine[Any, Any, StreamRecord],
        *,
        on_success: SuccessCallback | None,
        on_error: ErrorCallback | None,
    ) -> concurrent.futures.Future[StreamRecord]:
        future = self._runner.submit(coroutine)

        def completed(value: concurrent.futures.Future[StreamRecord]) -> None:
            try:
                result = value.result()
            except BaseException as exc:
                if on_error is not None:
                    on_error(exc)
            else:
                if on_success is not None:
                    on_success(result)

        future.add_done_callback(completed)
        return future
