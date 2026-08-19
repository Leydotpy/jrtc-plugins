from __future__ import annotations


class StreamingError(Exception):
    """Base exception exposed by jrtc-stream."""


class StreamingNotStarted(StreamingError):
    pass


class StreamingTimeout(StreamingError):
    def __init__(self, operation: str, timeout: float) -> None:
        super().__init__(f"{operation!r} timed out after {timeout:.1f}s")
        self.operation = operation
        self.timeout = timeout


class StreamingBackendError(StreamingError):
    pass


class StreamingProtocolError(StreamingError):
    pass


class JanusCommandError(StreamingError):
    def __init__(self, code: int | None, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


class InvalidViewerState(StreamingError):
    def __init__(self, current: object, expected: tuple[object, ...]) -> None:
        expected_text = ", ".join(str(value) for value in expected)
        super().__init__(f"viewer is in state {current!s}; expected one of: {expected_text}")
        self.current = current
        self.expected = expected
