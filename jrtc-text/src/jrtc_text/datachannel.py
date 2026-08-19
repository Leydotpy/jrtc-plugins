"""Bounded DataChannel transaction manager for TextRoom JSON messages."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable
from typing import Any, Protocol, runtime_checkable

from .errors import (
    TextRoomBackpressureError,
    TextRoomChannelClosed,
    TextRoomChannelNotOpen,
    TextRoomPluginError,
    TextRoomProtocolError,
    TextRoomTransactionTimeout,
)
from .models import (
    ChatMessageRequest,
    TextRoomDataRequest,
    TextRoomErrorResponse,
    TextRoomResponse,
    parse_textroom_data_response,
)


@runtime_checkable
class DataChannelLike(Protocol):
    """Minimal adapter expected from an application's WebRTC DataChannel.

    Adapters expose a normalized ``ready_state`` value and may implement
    ``send`` synchronously or asynchronously. The application forwards each
    received text payload to :meth:`TextRoomDataChannel.feed_data`.
    """

    ready_state: str

    def send(self, data: str) -> None | Awaitable[None]: ...


class TextRoomDataChannel:
    """Correlate transactions while bounding memory and request lifetimes."""

    def __init__(
        self,
        channel: DataChannelLike,
        *,
        default_timeout: float = 10.0,
        max_pending: int = 256,
        max_events: int = 512,
        max_message_bytes: int = 1_048_576,
    ) -> None:
        if default_timeout <= 0:
            raise ValueError("default_timeout must be positive")
        if max_pending <= 0 or max_events <= 0 or max_message_bytes <= 0:
            raise ValueError("DataChannel bounds must be positive")
        self._channel = channel
        self._default_timeout = default_timeout
        self._max_pending = max_pending
        self._max_message_bytes = max_message_bytes
        self._pending: dict[str, asyncio.Future[TextRoomResponse]] = {}
        self._events: asyncio.Queue[TextRoomResponse] = asyncio.Queue(maxsize=max_events)
        self._closed = False
        self._dropped_events = 0
        self._late_responses = 0

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def dropped_events(self) -> int:
        return self._dropped_events

    @property
    def late_responses(self) -> int:
        return self._late_responses

    @property
    def closed(self) -> bool:
        return self._closed

    def _ensure_open(self) -> None:
        if self._closed:
            raise TextRoomChannelClosed("TextRoom DataChannel manager is closed")
        if self._channel.ready_state.lower() != "open":
            raise TextRoomChannelNotOpen(
                f"TextRoom DataChannel state is {self._channel.ready_state!r}, not 'open'"
            )

    async def request(
        self,
        message: TextRoomDataRequest,
        *,
        timeout: float | None = None,
        expect_response: bool | None = None,
    ) -> TextRoomResponse | None:
        """Send one request and await its transaction response when applicable."""

        self._ensure_open()
        deadline = self._default_timeout if timeout is None else timeout
        if deadline <= 0:
            raise ValueError("timeout must be positive")
        if expect_response is None:
            expect_response = not (isinstance(message, ChatMessageRequest) and message.ack is False)

        transaction = message.transaction
        future: asyncio.Future[TextRoomResponse] | None = None
        if expect_response:
            if len(self._pending) >= self._max_pending:
                raise TextRoomBackpressureError(
                    f"at most {self._max_pending} TextRoom transactions may be pending"
                )
            if transaction in self._pending:
                raise TextRoomProtocolError(f"duplicate transaction {transaction!r}")
            future = asyncio.get_running_loop().create_future()
            self._pending[transaction] = future

        payload = json.dumps(
            message.model_dump(mode="json", by_alias=True, exclude_none=True),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if len(payload.encode("utf-8")) > self._max_message_bytes:
            if future is not None:
                self._pending.pop(transaction, None)
                future.cancel()
            raise TextRoomProtocolError("outbound TextRoom message exceeds size limit")

        try:
            sent = self._channel.send(payload)
            if inspect.isawaitable(sent):
                await sent
        except BaseException:
            if future is not None:
                self._pending.pop(transaction, None)
                future.cancel()
            raise

        if future is None:
            return None
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=deadline)
        except asyncio.CancelledError:
            if self._pending.get(transaction) is future:
                self._pending.pop(transaction, None)
            future.cancel()
            raise
        except TimeoutError as exc:
            if self._pending.get(transaction) is future:
                self._pending.pop(transaction, None)
            future.cancel()
            raise TextRoomTransactionTimeout(transaction, deadline) from exc

    def feed_data(self, payload: str | bytes | bytearray | memoryview) -> TextRoomResponse:
        """Consume one incoming UTF-8 JSON payload on the owning event loop."""

        if self._closed:
            raise TextRoomChannelClosed("TextRoom DataChannel manager is closed")
        if isinstance(payload, str):
            raw_bytes = payload.encode("utf-8")
            text = payload
        elif isinstance(payload, (bytes, bytearray, memoryview)):
            raw_bytes = bytes(payload)
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise TextRoomProtocolError("TextRoom only accepts UTF-8 text frames") from exc
        else:
            raise TextRoomProtocolError("TextRoom DataChannel payload must be text or bytes")
        if len(raw_bytes) > self._max_message_bytes:
            raise TextRoomProtocolError("inbound TextRoom message exceeds size limit")
        try:
            decoded: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            raise TextRoomProtocolError("invalid TextRoom DataChannel JSON") from exc
        if not isinstance(decoded, dict):
            raise TextRoomProtocolError("TextRoom DataChannel JSON must be an object")

        transaction = decoded.get("transaction")
        try:
            parsed = parse_textroom_data_response(decoded, raise_errors=False)
        except TextRoomProtocolError as exc:
            if isinstance(transaction, str):
                future = self._pending.pop(transaction, None)
                if future is not None and not future.done():
                    future.set_exception(exc)
            raise
        if isinstance(transaction, str):
            future = self._pending.pop(transaction, None)
            if future is None:
                self._late_responses += 1
            elif isinstance(parsed, TextRoomErrorResponse):
                future.set_exception(
                    TextRoomPluginError(
                        parsed.error_code,
                        parsed.error,
                        transaction=transaction,
                        raw=decoded,
                    )
                )
            else:
                future.set_result(parsed)
            return parsed

        if self._events.full():
            self._events.get_nowait()
            self._dropped_events += 1
        self._events.put_nowait(parsed)
        return parsed

    async def next_event(self, *, timeout: float | None = None) -> TextRoomResponse:
        """Wait for the next unsolicited join/leave/message/admin event."""

        if self._closed and self._events.empty():
            raise TextRoomChannelClosed("TextRoom DataChannel manager is closed")
        if timeout is None:
            return await self._events.get()
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        return await asyncio.wait_for(self._events.get(), timeout=timeout)

    async def aclose(self) -> None:
        """Close deterministically and fail every outstanding transaction."""

        if self._closed:
            return
        self._closed = True
        pending, self._pending = self._pending, {}
        for future in pending.values():
            if not future.done():
                future.set_exception(
                    TextRoomChannelClosed("TextRoom DataChannel manager was closed")
                )

    async def __aenter__(self) -> TextRoomDataChannel:
        self._ensure_open()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.aclose()
