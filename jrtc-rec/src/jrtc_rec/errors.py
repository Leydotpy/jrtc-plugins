"""Typed Record&Play failures."""

from __future__ import annotations

from typing import Any

from logvista import get_logger


logger = get_logger(__name__)


class RecordPlayError(Exception):
    """Base class for Record&Play failures."""


class RecordPlayProtocolError(RecordPlayError):
    """A JSEP or response object violated the protocol contract."""


class RecordPlayJanusError(RecordPlayError):
    """The outer Janus API returned an error."""

    def __init__(self, code: int, reason: str, *, transaction: str | None = None) -> None:
        super().__init__(f"Janus error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction

        logger.error(f"Janus error {code}", reason, context={
            "transaction": transaction,
        })




class RecordPlayPluginError(RecordPlayError):
    """The Record&Play plugin returned a plugin-level error."""

    def __init__(
        self,
        code: int,
        reason: str,
        *,
        transaction: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"Record&Play error {code}: {reason}")
        self.code = code
        self.reason = reason
        self.transaction = transaction
        self.raw = raw

        logger.error(f"Record&Play error {code}", reason, context={
            "transaction": transaction,
            "raw": raw,
        })
