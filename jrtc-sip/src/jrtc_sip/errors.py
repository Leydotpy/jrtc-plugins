"""Typed failures raised by :mod:`janus_sip_plugin`."""

from __future__ import annotations

from typing import Any


class SipError(Exception):
    """Base class for SIP client failures."""


class SipProtocolError(SipError):
    """A local JSEP, request invariant, or response shape was invalid."""


class SipJanusError(SipError):
    """The outer Janus API returned an error envelope."""

    def __init__(self, code: int, reason: str, *, transaction: str | None = None) -> None:
        super().__init__(f"Janus error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction


class SipPluginError(SipError):
    """The SIP plugin rejected a plugin API request."""

    def __init__(
        self,
        code: int,
        reason: str,
        *,
        transaction: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"SIP plugin error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction
        self.raw = raw
