"""Typed VideoCall client failures."""

from __future__ import annotations

from typing import Any


class VideoCallError(Exception):
    """Base class for VideoCall failures."""


class VideoCallProtocolError(VideoCallError):
    """A JSEP or response object violated the documented protocol."""


class VideoCallJanusError(VideoCallError):
    """The outer Janus API returned an error."""

    def __init__(self, code: int, reason: str, *, transaction: str | None = None) -> None:
        super().__init__(f"Janus error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction


class VideoCallPluginError(VideoCallError):
    """The VideoCall plugin returned a plugin-level error."""

    def __init__(
        self,
        code: int,
        reason: str,
        *,
        transaction: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"VideoCall error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction
        self.raw = raw
