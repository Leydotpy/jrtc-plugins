from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from stream_orchestrator import (
    MediaKind,
    PipelineSpec,
    RtpTarget,
    SourceContext,
    SourceSpec,
    StreamDefinition,
    TrackContract,
)

from stream_orchestrator_ffmpeg import FfmpegCommandBuilder, default_profiles


def make_context():
    return SourceContext(
        stream_id=uuid4(),
        generation=1,
        startup_timeout_seconds=30,
        targets=(
            RtpTarget(
                mid="video",
                kind=MediaKind.VIDEO,
                host="10.0.0.10",
                rtp_port=5004,
                rtcp_port=5005,
                payload_type=96,
                codec="h264",
            ),
            RtpTarget(
                mid="audio",
                kind=MediaKind.AUDIO,
                host="10.0.0.10",
                rtp_port=5006,
                rtcp_port=5007,
                payload_type=111,
                codec="opus",
            ),
        ),
    )


def make_definition(locator="rtsp://camera.example/live"):
    return StreamDefinition(
        name="camera",
        source=SourceSpec(kind="rtsp", locator=locator, settings={"transport": "tcp"}),
        pipeline=PipelineSpec(driver="ffmpeg", profile="h264-opus-low-latency"),
        tracks=(
            TrackContract("video", MediaKind.VIDEO, "h264", 96, 90_000),
            TrackContract("audio", MediaKind.AUDIO, "opus", 111, 48_000, 2),
        ),
    )


def test_builder_uses_argument_vector_and_one_output_per_track():
    spec = FfmpegCommandBuilder(profiles=default_profiles()).build(
        make_context(), make_definition()
    )
    assert spec.argv[0] == "ffmpeg"
    assert "-nostdin" in spec.argv
    assert "-rtsp_transport" in spec.argv
    assert spec.argv.count("-f") == 2
    assert "rtp://10.0.0.10:5004?pkt_size=1200" in spec.argv
    assert "rtp://10.0.0.10:5006?pkt_size=1200" in spec.argv


def test_file_root_is_enforced(tmp_path: Path):
    builder = FfmpegCommandBuilder(
        profiles=default_profiles(),
        allowed_file_roots=(tmp_path / "allowed",),
    )
    with pytest.raises(PermissionError):
        builder.build(make_context(), make_definition("file:///etc/passwd"))
