"""Composition root fragment for a Django worker or ASGI lifespan hook."""

from __future__ import annotations

from janus_stream_orchestrator import JanusBackendSettings, JanusStreamingMountpointBackend
from janus_streaming import StreamingAdminClient
from stream_orchestrator import (
    InMemoryLockManager,
    OrchestratorService,
    SourceDriverRegistry,
    StreamController,
    SystemClock,
)
from stream_orchestrator_django.events import DjangoEventPublisher
from stream_orchestrator_django.repository import DjangoStreamRepository


def build_django_service(
    *,
    admin: StreamingAdminClient,
    drivers: SourceDriverRegistry,
) -> OrchestratorService:
    repository = DjangoStreamRepository()
    clock = SystemClock()
    controller = StreamController(
        repository=repository,
        mountpoints=JanusStreamingMountpointBackend(
            admin,
            settings=JanusBackendSettings(rtp_host="janus.internal"),
        ),
        drivers=drivers,
        # Replace with a fenced distributed implementation for multi-worker use.
        locks=InMemoryLockManager(),
        events=DjangoEventPublisher(outbox_topic="stream.lifecycle"),
        clock=clock,
    )
    return OrchestratorService(
        repository=repository,
        controller=controller,
        clock=clock,
    )
