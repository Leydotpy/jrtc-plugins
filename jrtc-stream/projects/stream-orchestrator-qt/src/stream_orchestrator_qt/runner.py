from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


class AsyncioLoopThread:
    """Own one asyncio event loop in a dedicated, restartable thread."""

    def __init__(self, *, name: str = "stream-orchestrator") -> None:
        self._name = name
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._lock = threading.RLock()

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive() and self._loop is not None

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._run,
                name=self._name,
                daemon=True,
            )
            self._thread.start()
        if not self._ready.wait(timeout=10.0):
            raise RuntimeError("asyncio service thread did not start")

    def submit(self, coroutine: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
        self.start()
        loop = self._loop
        if loop is None:
            coroutine.close()
            raise RuntimeError("asyncio service loop is unavailable")
        return asyncio.run_coroutine_threadsafe(coroutine, loop)

    def stop(self, *, timeout: float = 10.0) -> None:
        with self._lock:
            loop = self._loop
            thread = self._thread
            if loop is None or thread is None:
                return
            loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=timeout)
        if thread.is_alive():
            raise RuntimeError("asyncio service thread did not stop")
        with self._lock:
            self._thread = None
            self._loop = None

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lock:
            self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
            loop.close()
