from __future__ import annotations

from uuid import uuid4

from stream_orchestrator import (
    MediaKind,
    PipelineSpec,
    RtpTarget,
    SourceContext,
    SourceSpec,
    StreamDefinition,
    TrackContract,
)

from stream_orchestrator_gstreamer import GstreamerCommandBuilder, default_profiles


def test_builder_creates_structured_audio_and_video_branches():
    definition = StreamDefinition(
        name="camera",
        source=SourceSpec(kind="rtsp", locator="rtsp://camera.example/live"),
        pipeline=PipelineSpec(driver="gstreamer", profile="h264-opus-low-latency"),
        tracks=(
            TrackContract("video", MediaKind.VIDEO, "h264", 96, 90_000),
            TrackContract("audio", MediaKind.AUDIO, "opus", 111, 48_000, 2),
        ),
    )
    context = SourceContext(
        stream_id=uuid4(),
        generation=2,
        startup_timeout_seconds=30,
        targets=(
            RtpTarget("video", MediaKind.VIDEO, "10.0.0.8", 6000, 6001, 96, "h264"),
            RtpTarget("audio", MediaKind.AUDIO, "10.0.0.8", 6002, 6003, 111, "opus"),
        ),
    )
    spec = GstreamerCommandBuilder(profiles=default_profiles()).build(context, definition)
    assert spec.argv[0] == "gst-launch-1.0"
    assert "rtph264pay" in spec.argv
    assert "rtpopuspay" in spec.argv
    assert "port=6000" in spec.argv
    assert "port=6002" in spec.argv
