from __future__ import annotations

from asgiref.sync import sync_to_async
from django.db import transaction
from stream_orchestrator import StreamEvent
from stream_orchestrator.serde import event_to_dict

from .models import OrchestratorEvent, OrchestratorOutbox


class DjangoEventPublisher:
    """Persist lifecycle events and an optional outbox row atomically."""

    def __init__(self, *, outbox_topic: str | None = None) -> None:
        self._outbox_topic = outbox_topic

    async def publish(self, event: StreamEvent) -> None:
        await sync_to_async(self._persist, thread_sensitive=True)(event)

    def _persist(self, event: StreamEvent) -> None:
        payload = event_to_dict(event)
        with transaction.atomic():
            OrchestratorEvent.objects.create(
                id=event.id,
                stream_id=event.stream_id,
                kind=event.kind,
                generation=event.generation,
                data=dict(event.data),
                occurred_at=event.occurred_at,
            )
            if self._outbox_topic is not None:
                OrchestratorOutbox.objects.create(
                    topic=self._outbox_topic,
                    stream_id=event.stream_id,
                    payload=payload,
                )
