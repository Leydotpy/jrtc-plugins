from __future__ import annotations

from uuid import uuid4

import pytest
from janus_streaming import CreatedMountpoint, CreatedPort, MountpointInfo, MountpointTrack
from stream_orchestrator import (
    MediaKind,
    PipelineSpec,
    SourceSpec,
    StreamDefinition,
    TrackContract,
)

from janus_stream_orchestrator import (
    JanusBackendSettings,
    JanusStreamingMountpointBackend,
    NativeRtspSourceDriver,
)


class FakeAdmin:
    def __init__(self, *, ports: tuple[CreatedPort, ...] | None = None) -> None:
        self.created = None
        self.enabled: list[int] = []
        self.ports = ports or (
            CreatedPort(type="audio", mid="audio", port=5004),
            CreatedPort(type="video", mid="video", port=5006),
        )

    async def create_rtp(self, spec):
        self.created = spec
        return CreatedMountpoint(
            id=77,
            type="rtp",
            ports=self.ports,
        )

    async def create_rtsp(self, spec):
        self.created = spec
        return CreatedMountpoint(id=78, type="rtsp")

    async def info(self, mountpoint_id: int, *, secret=None):
        assert mountpoint_id == 77
        return MountpointInfo(
            id=77,
            type="rtp",
            enabled=True,
            viewers=3,
            media=(
                MountpointTrack(mid="audio", type="audio", age_ms=4),
                MountpointTrack(mid="video", type="video", age_ms=7),
            ),
        )

    async def enable(self, mountpoint_id: int, *, secret=None):
        self.enabled.append(mountpoint_id)

    async def disable(self, *args, **kwargs):
        return None

    async def kick_all(self, *args, **kwargs):
        return None

    async def destroy(self, *args, **kwargs):
        return None


def definition() -> StreamDefinition:
    return StreamDefinition(
        id=uuid4(),
        name="Main",
        source=SourceSpec(kind="uri", locator="file:///media/main.mp4"),
        pipeline=PipelineSpec(driver="ffmpeg", profile="h264-opus-low-latency"),
        tracks=(
            TrackContract("audio", MediaKind.AUDIO, "opus", 111, 48_000, 2),
            TrackContract("video", MediaKind.VIDEO, "h264", 96, 90_000),
        ),
    )


@pytest.mark.asyncio
async def test_rtp_translation_and_inspection() -> None:
    admin = FakeAdmin()
    backend = JanusStreamingMountpointBackend(
        admin, settings=JanusBackendSettings(rtp_host="janus.internal")
    )
    ref = await backend.create(definition(), generation=2)
    assert ref.instance_id == "77"
    assert [target.rtp_port for target in ref.targets] == [5004, 5006]
    assert admin.created.enabled is False

    observation = await backend.inspect(ref)
    assert observation.exists
    assert observation.enabled
    assert observation.viewer_count == 3
    assert {track.mid for track in observation.tracks} == {"audio", "video"}


@pytest.mark.asyncio
async def test_native_rtsp_driver_is_framework_neutral() -> None:
    definition_value = StreamDefinition(
        name="Camera",
        source=SourceSpec(kind="rtsp", locator="rtsp://camera/live"),
        pipeline=PipelineSpec(driver="janus-native-rtsp"),
        tracks=(),
    )
    driver = NativeRtspSourceDriver()
    from stream_orchestrator import SourceContext

    prepared = await driver.prepare(
        SourceContext(definition_value.id, 1, (), 20.0), definition_value
    )
    ref = await driver.start(prepared, generation=1)
    observation = await driver.inspect(ref)
    assert observation.healthy


@pytest.mark.asyncio
async def test_rtp_translation_rejects_duplicate_returned_mids() -> None:
    admin = FakeAdmin(
        ports=(
            CreatedPort(type="audio", mid="audio", port=5004),
            CreatedPort(type="audio", mid="audio", port=5006),
        )
    )
    backend = JanusStreamingMountpointBackend(
        admin, settings=JanusBackendSettings(rtp_host="janus.internal")
    )

    with pytest.raises(RuntimeError, match="duplicate RTP target"):
        await backend.create(definition(), generation=1)


@pytest.mark.asyncio
async def test_native_rtsp_settings_require_typed_values() -> None:
    admin = FakeAdmin()
    backend = JanusStreamingMountpointBackend(
        admin, settings=JanusBackendSettings(rtp_host="janus.internal")
    )
    definition_value = StreamDefinition(
        name="Camera",
        source=SourceSpec(
            kind="rtsp",
            locator="rtsp://camera/live",
            settings={"notify_changes": "false"},
        ),
        pipeline=PipelineSpec(driver="janus-native-rtsp"),
        tracks=(),
    )

    with pytest.raises(TypeError, match="notify_changes must be a boolean"):
        await backend.create(definition_value, generation=1)


def test_backend_settings_reject_negative_values() -> None:
    with pytest.raises(ValueError, match="threads must not be negative"):
        JanusBackendSettings(rtp_host="janus.internal", threads=-1)
