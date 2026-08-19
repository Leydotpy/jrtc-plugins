from __future__ import annotations

from dataclasses import replace

import pytest
from stream_orchestrator import (
    ConcurrencyConflict,
    MediaKind,
    PipelineSpec,
    SourceSpec,
    StreamDefinition,
    StreamEvent,
    StreamRecord,
    StreamStatus,
    TrackContract,
)

from stream_orchestrator_django.events import DjangoEventPublisher
from stream_orchestrator_django.models import OrchestratorEvent, OrchestratorOutbox
from stream_orchestrator_django.repository import DjangoStreamRepository


def definition() -> StreamDefinition:
    return StreamDefinition(
        name="camera",
        source=SourceSpec(kind="rtsp", locator="rtsp://camera/live"),
        pipeline=PipelineSpec(driver="ffmpeg", profile="h264"),
        tracks=(
            TrackContract(
                mid="video",
                kind=MediaKind.VIDEO,
                codec="h264",
                payload_type=96,
                clock_rate=90_000,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_repository_round_trip_and_compare_and_swap() -> None:
    repository = DjangoStreamRepository()
    value = definition()
    original = StreamRecord(
        definition=value,
        status=StreamStatus(stream_id=value.id),
    )

    created = await repository.create(original)
    assert await repository.get(created.id) == created

    updated = await repository.save(
        replace(created, status=replace(created.status, reason_code="updated")),
        expected_revision=0,
    )
    assert updated.revision == 1
    assert (await repository.get(created.id)).status.reason_code == "updated"

    with pytest.raises(ConcurrencyConflict):
        await repository.save(created, expected_revision=0)


@pytest.mark.asyncio
async def test_event_and_outbox_are_persisted() -> None:
    value = definition()
    event = StreamEvent(
        kind="stream.ready",
        stream_id=value.id,
        generation=3,
        data={"mountpoint_id": "1200"},
    )
    publisher = DjangoEventPublisher(outbox_topic="stream.lifecycle")

    await publisher.publish(event)

    stored_event = await OrchestratorEvent.objects.aget(pk=event.id)
    stored_outbox = await OrchestratorOutbox.objects.aget(stream_id=value.id)
    assert stored_event.kind == "stream.ready"
    assert stored_outbox.topic == "stream.lifecycle"
    assert stored_outbox.payload["id"] == str(event.id)
