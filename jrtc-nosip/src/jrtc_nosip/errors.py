"""Typed failures for the NoSIP client."""

from __future__ import annotations

from typing import Any


class NoSipError(Exception):
    """Base class for NoSIP failures."""


class NoSipProtocolError(NoSipError):
    """A request-side JSEP or response violated the protocol contract."""


class NoSipJanusError(NoSipError):
    """The outer Janus API returned an error response."""

    def __init__(self, code: int, reason: str, *, transaction: str | None = None) -> None:
        super().__init__(f"Janus error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction


class NoSipPluginError(NoSipError):
    """The NoSIP plugin returned an error response."""

    def __init__(
        self,
        code: int,
        reason: str,
        *,
        transaction: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"NoSIP error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction
        self.raw = raw
