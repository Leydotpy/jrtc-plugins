"""Typed failures raised by :mod:`janus_echotest_plugin`."""

from __future__ import annotations

from typing import Any


class EchoTestError(Exception):
    """Base class for all EchoTest client failures."""


class EchoTestProtocolError(EchoTestError):
    """A response or JSEP object violated the expected wire contract."""


class EchoTestJanusError(EchoTestError):
    """The outer Janus API returned an error envelope."""

    def __init__(self, code: int, reason: str, *, transaction: str | None = None) -> None:
        super().__init__(f"Janus error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction


class EchoTestPluginError(EchoTestError):
    """The EchoTest plugin returned ``error_code`` and ``error``."""

    def __init__(
        self,
        code: int,
        reason: str,
        *,
        transaction: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"EchoTest error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction
        self.raw = raw
