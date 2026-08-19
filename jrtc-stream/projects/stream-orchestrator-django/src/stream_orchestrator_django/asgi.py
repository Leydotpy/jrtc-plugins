from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol


class AsyncLifecycle(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...


AsgiReceive = Callable[[], Awaitable[dict[str, Any]]]
AsgiSend = Callable[[dict[str, Any]], Awaitable[None]]
AsgiApp = Callable[[dict[str, Any], AsgiReceive, AsgiSend], Awaitable[None]]


class LifespanApplication:
    """ASGI lifespan wrapper for an application-composed orchestration runtime."""

    def __init__(self, app: AsgiApp, lifecycle: AsyncLifecycle) -> None:
        self._app = app
        self._lifecycle = lifecycle

    async def __call__(self, scope: dict[str, Any], receive: AsgiReceive, send: AsgiSend) -> None:
        if scope.get("type") != "lifespan":
            await self._app(scope, receive, send)
            return

        while True:
            message = await receive()
            message_type = message["type"]
            if message_type == "lifespan.startup":
                try:
                    await self._lifecycle.start()
                except Exception as exc:
                    await send({"type": "lifespan.startup.failed", "message": str(exc)})
                    return
                await send({"type": "lifespan.startup.complete"})
            elif message_type == "lifespan.shutdown":
                try:
                    await self._lifecycle.stop()
                except Exception as exc:
                    await send({"type": "lifespan.shutdown.failed", "message": str(exc)})
                    return
                await send({"type": "lifespan.shutdown.complete"})
                return
