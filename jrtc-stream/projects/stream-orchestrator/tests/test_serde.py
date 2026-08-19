from __future__ import annotations

from stream_orchestrator import MediaKind, PipelineSpec, SourceSpec, StreamDefinition, TrackContract
from stream_orchestrator.serde import definition_from_dict, definition_to_dict


def test_definition_round_trip():
    value = StreamDefinition(
        name="camera",
        source=SourceSpec(kind="rtsp", locator="rtsp://camera/live", settings={"tcp": True}),
        pipeline=PipelineSpec(driver="ffmpeg", profile="h264-opus"),
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
    rebuilt = definition_from_dict(definition_to_dict(value))
    assert rebuilt == value
