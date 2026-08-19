"""Qt-facing usage without coupling the service to a Qt binding."""

from __future__ import annotations

from uuid import UUID

from stream_orchestrator import OrchestratorService
from stream_orchestrator_qt import CallbackOrchestratorBridge


def make_bridge(service: OrchestratorService) -> CallbackOrchestratorBridge:
    return CallbackOrchestratorBridge(service)


def start_from_ui(bridge: CallbackOrchestratorBridge, stream_id: UUID) -> None:
    bridge.start_stream(
        stream_id,
        on_success=lambda record: print(record.status.operational),
        on_error=lambda error: print(f"start failed: {error}"),
    )
