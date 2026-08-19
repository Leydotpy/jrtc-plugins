from __future__ import annotations

from uuid import UUID

from .bridge import CallbackOrchestratorBridge


def create_qobject_bridge(bridge: CallbackOrchestratorBridge) -> object:
    """Create a PyQt6 QObject whose queued signals enter the GUI thread."""

    try:
        from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
    except ImportError as exc:
        raise RuntimeError("install stream-orchestrator-qt[pyqt6]") from exc

    class OrchestratorQObject(QObject):
        succeeded = pyqtSignal(object)
        failed = pyqtSignal(str)

        @pyqtSlot(str)
        def start_stream(self, stream_id: str) -> None:
            bridge.start_stream(
                UUID(stream_id),
                on_success=self.succeeded.emit,
                on_error=lambda error: self.failed.emit(str(error)),
            )

        @pyqtSlot(str)
        def stop_stream(self, stream_id: str) -> None:
            bridge.stop_stream(
                UUID(stream_id),
                on_success=self.succeeded.emit,
                on_error=lambda error: self.failed.emit(str(error)),
            )

        @pyqtSlot(str)
        def refresh(self, stream_id: str) -> None:
            bridge.refresh(
                UUID(stream_id),
                on_success=self.succeeded.emit,
                on_error=lambda error: self.failed.emit(str(error)),
            )

    return OrchestratorQObject()
