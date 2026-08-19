from __future__ import annotations

from uuid import UUID

from .bridge import CallbackOrchestratorBridge


def create_qobject_bridge(bridge: CallbackOrchestratorBridge) -> object:
    """Create a PySide6 QObject whose queued signals enter the GUI thread."""

    try:
        from PySide6.QtCore import QObject, Signal, Slot
    except ImportError as exc:
        raise RuntimeError("install stream-orchestrator-qt[pyside6]") from exc

    class OrchestratorQObject(QObject):
        succeeded = Signal(object)
        failed = Signal(str)

        @Slot(str)
        def start_stream(self, stream_id: str) -> None:
            bridge.start_stream(
                UUID(stream_id),
                on_success=self.succeeded.emit,
                on_error=lambda error: self.failed.emit(str(error)),
            )

        @Slot(str)
        def stop_stream(self, stream_id: str) -> None:
            bridge.stop_stream(
                UUID(stream_id),
                on_success=self.succeeded.emit,
                on_error=lambda error: self.failed.emit(str(error)),
            )

        @Slot(str)
        def refresh(self, stream_id: str) -> None:
            bridge.refresh(
                UUID(stream_id),
                on_success=self.succeeded.emit,
                on_error=lambda error: self.failed.emit(str(error)),
            )

    return OrchestratorQObject()
