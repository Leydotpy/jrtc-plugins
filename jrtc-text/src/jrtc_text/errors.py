"""Typed TextRoom and DataChannel lifecycle failures."""

from __future__ import annotations

from typing import Any


class TextRoomError(Exception):
    """Base class for TextRoom failures."""


class TextRoomProtocolError(TextRoomError):
    """A request, response, JSEP, or DataChannel payload was invalid."""


class TextRoomJanusError(TextRoomError):
    """The outer Janus API returned an error."""

    def __init__(self, code: int, reason: str, *, transaction: str | None = None) -> None:
        super().__init__(f"Janus error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction


class TextRoomPluginError(TextRoomError):
    """The TextRoom plugin rejected a Janus or DataChannel request."""

    def __init__(
        self,
        code: int,
        reason: str,
        *,
        transaction: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"TextRoom error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction
        self.raw = raw


class TextRoomChannelClosed(TextRoomError):
    """The bounded DataChannel transaction manager is closed."""


class TextRoomChannelNotOpen(TextRoomError):
    """The bound DataChannel is not in its open state."""


class TextRoomBackpressureError(TextRoomError):
    """The configured maximum number of pending transactions was reached."""


class TextRoomTransactionTimeout(TextRoomError, TimeoutError):
    """A DataChannel response was not received within its deadline."""

    def __init__(self, transaction: str, timeout: float) -> None:
        super().__init__(
            f"TextRoom transaction {transaction!r} timed out after {timeout:g} seconds"
        )
        self.transaction = transaction
        self.timeout = timeout
