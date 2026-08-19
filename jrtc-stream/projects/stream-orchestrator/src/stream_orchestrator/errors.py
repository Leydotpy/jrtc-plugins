from __future__ import annotations

from uuid import UUID


class OrchestratorError(Exception):
    """Base exception exposed by the orchestration core."""


class StreamNotFound(OrchestratorError):
    def __init__(self, stream_id: UUID) -> None:
        super().__init__(f"stream {stream_id} does not exist")
        self.stream_id = stream_id


class StreamAlreadyExists(OrchestratorError):
    def __init__(self, stream_id: UUID) -> None:
        super().__init__(f"stream {stream_id} already exists")
        self.stream_id = stream_id


class ConcurrencyConflict(OrchestratorError):
    def __init__(self, stream_id: UUID, expected: int, actual: int) -> None:
        super().__init__(
            f"stream {stream_id} revision conflict: expected {expected}, actual {actual}"
        )
        self.stream_id = stream_id
        self.expected = expected
        self.actual = actual


class DriverNotRegistered(OrchestratorError):
    def __init__(self, driver: str) -> None:
        super().__init__(f"source driver {driver!r} is not registered")
        self.driver = driver


class GateNotRegistered(OrchestratorError):
    def __init__(self, kind: str) -> None:
        super().__init__(f"source readiness gate {kind!r} is not registered")
        self.kind = kind


class InvalidDefinition(OrchestratorError, ValueError):
    """A stream definition violates a domain invariant."""


class ReconciliationFailed(OrchestratorError):
    def __init__(self, stream_id: UUID, message: str) -> None:
        super().__init__(f"failed to reconcile stream {stream_id}: {message}")
        self.stream_id = stream_id
