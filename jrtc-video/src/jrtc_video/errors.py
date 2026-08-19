"""Typed failures raised by :mod:`janus_videoroom_plugin`."""

from __future__ import annotations

from typing import Any

from logvista import get_logger

logger = get_logger(__name__)


class VideoRoomError(Exception):
    """Base class for VideoRoom client failures."""


class VideoRoomProtocolError(VideoRoomError):
    """A request combination, JSEP, or response violated the protocol."""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(message)
        self.message = message
        logger.error(
            "Janus protocol error",
            message,
        )


class VideoRoomJanusError(VideoRoomError):
    """The outer Janus API returned an error envelope."""

    def __init__(
        self, code: int, reason: str, *, transaction: str | None = None
    ) -> None:
        super().__init__(f"Janus error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction

        logger.error(
            f"Janus room error {code}",
            reason,
            context={"transaction": transaction, "code": code},
        )


class VideoRoomPluginError(VideoRoomError):
    """The VideoRoom plugin returned ``error_code`` and ``error``."""

    def __init__(
        self,
        code: int,
        reason: str,
        *,
        transaction: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"VideoRoom error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction
        self.raw = raw

        logger.error(
            "Janus plugin error",
            reason,
            context={"transaction": transaction, "code": code, "raw": raw},
        )


class VideoRoomLifecycleError(VideoRoomError):
    """A service-owned publisher/subscriber was used in an invalid state."""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(message)
        self.message = message
        logger.error(
            "Janus lifecycle error",
            message,
        )
