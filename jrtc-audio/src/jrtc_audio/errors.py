"""Typed failures raised by :mod:`janus_audiobridge_plugin`."""

from __future__ import annotations

from typing import Any


class AudioBridgeError(Exception):
    """Base class for AudioBridge client failures."""


class AudioBridgeProtocolError(AudioBridgeError):
    """The response, request combination, or JSEP violated the protocol."""


class AudioBridgeJanusError(AudioBridgeError):
    """The outer Janus API returned an error envelope."""

    def __init__(
        self, code: int, reason: str, *, transaction: str | None = None
    ) -> None:
        super().__init__(f"Janus error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction


class AudioBridgePluginError(AudioBridgeError):
    """The AudioBridge plugin returned ``error_code`` and ``error``."""

    def __init__(
        self,
        code: int,
        reason: str,
        *,
        transaction: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"AudioBridge error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction
        self.raw = raw
