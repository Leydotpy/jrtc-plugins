from __future__ import annotations

import tomllib
from enum import IntEnum
from pathlib import Path

import pytest
from pydantic import ValidationError

from janus_streaming import (
    IceCandidate,
    RtspMountpointSpec,
    SessionDescription,
    StreamingPlugin,
    StreamingRuntimeSettings,
    _compat,
)
from janus_streaming.requests import (
    ConfigureRequest,
    ConfigureStream,
    CreateAudioMedia,
    CreateRequest,
    DestroyRequest,
    DisableRequest,
    EditRequest,
    EnableRequest,
    InfoRequest,
    KickAllRequest,
    ListRequest,
    PauseRequest,
    RecordingMedia,
    RecordingRequest,
    StartRequest,
    StopRequest,
    SwitchRequest,
    WatchRequest,
)
from janus_streaming.responses import (
    CreatedResponse,
    DestroyedResponse,
    EditedResponse,
    InfoResponse,
    KickedAllResponse,
    ListResponse,
    OkResponse,
    PausingResponse,
    PreparingResponse,
    StartingResponse,
    StoppingResponse,
    StreamingErrorResponse,
    SwitchedResponse,
)


def dumped(value):
    return value.model_dump(mode="json", by_alias=True, exclude_none=True)


def test_distribution_owns_plugin_class_and_entry_point() -> None:
    assert StreamingPlugin.__module__ == "janus_streaming._compat"
    assert StreamingPlugin.identifier == "streaming"
    assert StreamingPlugin.name == "janus.plugin.streaming"

    project_root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    assert "jrtc>=3.1,<4" in metadata["project"]["dependencies"]
    assert metadata["project"]["entry-points"]["jrtc.plugins"]["streaming"] == (
        "janus_streaming._compat:StreamingPlugin"
    )


class _IntSubclass(IntEnum):
    ONE = 1


@pytest.mark.parametrize("invalid", ["1", True, _IntSubclass.ONE])
def test_mountpoint_ids_are_strict_positive_integers(invalid: object) -> None:
    with pytest.raises(ValidationError):
        InfoRequest(id=invalid)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        CreatedResponse(
            create="created",
            stream={"id": invalid, "type": "rtp"},  # type: ignore[arg-type]
        )


def test_all_streaming_commands_use_extension_owned_models() -> None:
    requests = (
        ListRequest(),
        InfoRequest(id=1),
        CreateRequest(
            type="rtp",
            media=[CreateAudioMedia(mid="audio", port=5004, pt=111, codec="opus")],
        ),
        DestroyRequest(id=1),
        EditRequest(id=1),
        EnableRequest(id=1),
        DisableRequest(id=1),
        KickAllRequest(id=1),
        RecordingRequest(
            action="start",
            id=1,
            media=[RecordingMedia(mid="audio", filename="recordings/audio")],
        ),
        WatchRequest(id=1),
        StartRequest(),
        PauseRequest(),
        ConfigureRequest(streams=[ConfigureStream(mid="video", send=False)]),
        SwitchRequest(id=2),
        StopRequest(),
    )

    assert {request.request for request in requests} == {
        "configure",
        "create",
        "destroy",
        "disable",
        "edit",
        "enable",
        "info",
        "kick_all",
        "list",
        "pause",
        "recording",
        "start",
        "stop",
        "switch",
        "watch",
    }
    assert all(type(request).__module__ == "janus_streaming.requests" for request in requests)


def test_completed_trickle_has_the_janus_wire_shape() -> None:
    assert dumped(_compat.trickle_complete()) == {"completed": True}


def test_sensitive_values_are_hidden_from_model_representations() -> None:
    values = (
        SessionDescription(type="offer", sdp="sensitive-sdp"),
        IceCandidate(candidate="sensitive-candidate"),
        RtspMountpointSpec(
            url="rtsp://camera/live",
            secret="mount-secret",
            pin="viewer-pin",
            password="camera-password",
        ),
        StreamingRuntimeSettings(admin_key="admin-secret"),
    )

    rendered = " ".join(map(repr, values))
    assert "sensitive-sdp" not in rendered
    assert "sensitive-candidate" not in rendered
    assert "mount-secret" not in rendered
    assert "viewer-pin" not in rendered
    assert "camera-password" not in rendered
    assert "admin-secret" not in rendered


def test_all_streaming_response_models_are_extension_owned() -> None:
    responses = (
        ListResponse.model_validate({"streaming": "list", "list": []}),
        InfoResponse.model_validate(
            {"streaming": "info", "info": {"id": 1, "type": "rtp", "media": []}}
        ),
        CreatedResponse.model_validate(
            {
                "streaming": "created",
                "create": "camera",
                "stream": {"id": 1, "type": "rtsp"},
            }
        ),
        EditedResponse(id=1),
        DestroyedResponse(id=1),
        OkResponse(),
        KickedAllResponse(),
        PreparingResponse(),
        StartingResponse(),
        PausingResponse(),
        StoppingResponse(),
        SwitchedResponse(id=2),
        StreamingErrorResponse(error_code=455, error="No such mountpoint"),
    )

    assert all(type(response).__module__ == "janus_streaming.responses" for response in responses)
    # Janus responses are forward-compatible with additive fields.
    assert ListResponse.model_validate(
        {"streaming": "list", "list": [], "future_field": True}
    ).future_field


@pytest.mark.asyncio
async def test_concrete_plugin_owns_all_streaming_helpers(monkeypatch) -> None:
    captured = []

    async def fake_send(self, body, jsep=None, **kwargs):
        captured.append((body, jsep))
        return object()

    monkeypatch.setattr(StreamingPlugin, "send", fake_send)
    plugin = StreamingPlugin(session=object(), mountpoint=7, admin_key="admin-secret")

    await plugin.list()
    await plugin.info(secret="secret")
    await plugin.create(type="rtp", media=[CreateAudioMedia(mid="audio")])
    await plugin.destroy(secret="secret")
    await plugin.recording("start", [RecordingMedia(mid="audio", filename="recording")])
    await plugin.edit(new_is_private=False)
    await plugin.enable()
    await plugin.disable()
    await plugin.kick_all()
    await plugin.watch(media=["video", "video"])
    jsep = object()
    await plugin.start_streaming(jsep)
    await plugin.pause()
    await plugin.configure([ConfigureStream(mid="video", send=False)])
    await plugin.switch(8)
    await plugin.stop_streaming()
    await plugin.subscribe(media=["audio"])

    assert [body.request for body, _ in captured] == [
        "list",
        "info",
        "create",
        "destroy",
        "recording",
        "edit",
        "enable",
        "disable",
        "kick_all",
        "watch",
        "start",
        "pause",
        "configure",
        "switch",
        "stop",
        "watch",
    ]
    assert captured[2][0].admin_key == "admin-secret"
    assert captured[9][0].media == ["video"]
    assert captured[10][1] is jsep


@pytest.mark.asyncio
async def test_handle_attach_constructs_the_extension_class_directly(monkeypatch) -> None:
    observed = {}

    class FakeStreamingPlugin:
        id = 123

        def __init__(self, **kwargs):
            observed.update(kwargs)

        async def attach(self):
            return self

    monkeypatch.setattr(_compat, "StreamingPlugin", FakeStreamingPlugin)
    session = object()
    handle = await _compat.JanusStreamingHandle.attach(
        session,
        mountpoint_id=42,
        admin_key="not-constructor-state",
    )

    assert handle.handle_id == 123
    assert observed == {"session": session}
