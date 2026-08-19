from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import _compat
from .admin import StreamingAdminClient
from .errors import StreamingNotStarted
from .models import JanusId
from .viewer import StreamingViewer


@dataclass(frozen=True, slots=True)
class StreamingRuntimeSettings:
    admin_key: str | None = field(default=None, repr=False)
    request_timeout: float = 10.0
    negotiation_timeout: float = 15.0
    attach_timeout: float = 5.0
    max_admin_concurrency: int = 32

    def __post_init__(self) -> None:
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be greater than zero")
        if self.negotiation_timeout <= 0:
            raise ValueError("negotiation_timeout must be greater than zero")
        if self.attach_timeout <= 0:
            raise ValueError("attach_timeout must be greater than zero")
        if self.max_admin_concurrency < 1:
            raise ValueError("max_admin_concurrency must be at least one")


class StreamingRuntime:
    """Owns Streaming-plugin resources for an already-created Janus session."""

    def __init__(self, session: Any, settings: StreamingRuntimeSettings | None = None) -> None:
        self.session = session
        self.settings = settings or StreamingRuntimeSettings()
        self._admin: StreamingAdminClient | None = None
        self._viewers: set[StreamingViewer] = set()
        self._lock = asyncio.Lock()

    @property
    def admin(self) -> StreamingAdminClient:
        if self._admin is None:
            raise StreamingNotStarted("StreamingRuntime.start() has not been called")
        return self._admin

    async def start(self) -> None:
        async with self._lock:
            if self._admin is not None:
                return
            admin = StreamingAdminClient(
                self.session,
                admin_key=self.settings.admin_key,
                request_timeout=self.settings.request_timeout,
                attach_timeout=self.settings.attach_timeout,
                max_concurrency=self.settings.max_admin_concurrency,
            )
            await admin.start()
            self._admin = admin

    def create_viewer(self, mountpoint_id: JanusId, **kwargs: Any) -> StreamingViewer:
        viewer = StreamingViewer(
            self.session,
            mountpoint_id=mountpoint_id,
            request_timeout=self.settings.request_timeout,
            negotiation_timeout=self.settings.negotiation_timeout,
            attach_timeout=self.settings.attach_timeout,
            **kwargs,
        )
        self._viewers.add(viewer)
        return viewer

    async def release_viewer(self, viewer: StreamingViewer) -> None:
        try:
            await viewer.close()
        finally:
            self._viewers.discard(viewer)

    async def close(self) -> None:
        async with self._lock:
            admin, self._admin = self._admin, None
            viewers = tuple(self._viewers)
            self._viewers.clear()
        if viewers:
            await asyncio.gather(*(viewer.close() for viewer in viewers), return_exceptions=True)
        if admin is not None:
            await admin.close()


class ManagedStreamingRuntime:
    """Optional helper that also owns jrtc's session manager.

    The import is lazy so applications that inject an existing Janus session do
    not import a server framework or distributed session stack.
    """

    def __init__(
        self,
        settings: StreamingRuntimeSettings | None = None,
        *,
        manager_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.settings = settings or StreamingRuntimeSettings()
        self._manager_factory = manager_factory
        self._manager: Any | None = None
        self._runtime: StreamingRuntime | None = None

    @property
    def runtime(self) -> StreamingRuntime:
        if self._runtime is None:
            raise StreamingNotStarted("ManagedStreamingRuntime.start() has not been called")
        return self._runtime

    async def start(self) -> None:
        if self._runtime is not None:
            return
        if self._manager_factory is None:
            manager = _compat.create_session_manager()
        else:
            manager = self._manager_factory()
        await manager.start()
        session = manager.get_session()
        if session is None:
            await manager.stop()
            raise StreamingNotStarted("jrtc started without an available session")
        runtime = StreamingRuntime(session, self.settings)
        try:
            await runtime.start()
        except BaseException:
            await manager.stop()
            raise
        self._manager = manager
        self._runtime = runtime

    async def close(self) -> None:
        runtime, self._runtime = self._runtime, None
        manager, self._manager = self._manager, None
        if runtime is not None:
            await runtime.close()
        if manager is not None:
            await manager.stop()
