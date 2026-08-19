from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from uuid import UUID

from .controller import StreamController
from .ports import Clock, StreamRepository

logger = logging.getLogger(__name__)


class Reconciler:
    """Periodic, bounded-concurrency reconciliation loop.

    The caller owns lifecycle explicitly through `start()` and `stop()`.
    """

    def __init__(
        self,
        *,
        repository: StreamRepository,
        controller: StreamController,
        clock: Clock,
        interval_seconds: float = 2.0,
        max_concurrency: int = 16,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self._repository = repository
        self._controller = controller
        self._clock = clock
        self._interval = interval_seconds
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._wake = asyncio.Event()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="stream-orchestrator-reconciler")

    async def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    def wake(self) -> None:
        self._wake.set()

    async def reconcile_once(self) -> None:
        records = await self._repository.list()

        async def reconcile_one(stream_id: UUID) -> None:
            async with self._semaphore:
                try:
                    await self._controller.reconcile(stream_id)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "unhandled reconciliation error",
                        extra={"stream_id": str(stream_id)},
                    )

        async with asyncio.TaskGroup() as group:
            for record in records:
                group.create_task(reconcile_one(record.id))

    async def _run(self) -> None:
        while not self._stop.is_set():
            await self.reconcile_once()
            self._wake.clear()
            try:
                async with asyncio.timeout(self._interval):
                    await self._wake.wait()
            except TimeoutError:
                pass
