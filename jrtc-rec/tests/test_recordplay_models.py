from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from jrtc_rec import (
    Configured,
    ConfigureRequest,
    RecordingsList,
    RecordingsUpdated,
    RecordPlayEvent,
    RecordPlayPluginError,
    RecordRequest,
    UnknownRecordPlayResponse,
    UnknownRecordPlayResult,
    parse_recordplay_response,
)
from pydantic import ValidationError


def test_requests_serialize_exact_hyphenated_and_recording_fields() -> None:
    assert ConfigureRequest(video_bitrate_max=1_000_000, video_keyframe_interval=5).model_dump(
        by_alias=True, exclude_none=True
    ) == {
        "request": "configure",
        "video-bitrate-max": 1_000_000,
        "video-keyframe-interval": 5,
    }
    assert RecordRequest(
        id=77,
        name=" demo ",
        is_private=True,
        filename="recordings/demo",
        audiocodec="opus",
        videocodec="vp9",
        videoprofile="2",
        opusred=True,
        textdata=False,
        update=True,
    ).model_dump(exclude_none=True) == {
        "request": "record",
        "id": 77,
        "name": "demo",
        "is_private": True,
        "filename": "recordings/demo",
        "audiocodec": "opus",
        "videocodec": "vp9",
        "videoprofile": "2",
        "opusred": True,
        "textdata": False,
        "update": True,
    }
    with pytest.raises(ValidationError):
        ConfigureRequest()
    with pytest.raises(ValidationError):
        RecordRequest(name=" ")
    with pytest.raises(ValidationError):
        RecordRequest(name="demo", update=True)
    with pytest.raises(ValidationError):
        RecordRequest(name="demo", undocumented=True)  # type: ignore[call-arg]
    for invalid in ("77", True):
        with pytest.raises(ValidationError):
            RecordRequest(id=invalid, name="demo")  # type: ignore[arg-type]


def test_parser_covers_all_synchronous_response_shapes() -> None:
    listed = parse_recordplay_response(
        {
            "recordplay": "list",
            "list": [
                {
                    "id": 10,
                    "name": "Demo",
                    "date": "2026-07-11 12:00:00",
                    "audio": "demo-audio.mjr",
                    "audio_codec": "opus",
                    "future": "kept",
                }
            ],
        }
    )
    assert isinstance(listed.data, RecordingsList)
    assert listed.data.recordings[0].audio == "demo-audio.mjr"
    assert listed.data.recordings[0].model_extra == {"future": "kept"}
    assert isinstance(parse_recordplay_response({"recordplay": "ok"}).data, RecordingsUpdated)

    configured = parse_recordplay_response(
        {
            "recordplay": "configure",
            "status": "ok",
            "settings": {
                "video-bitrate-max": 1_000_000,
                "video-keyframe-interval": 5,
            },
        }
    )
    assert isinstance(configured.data, Configured)
    assert configured.data.settings.video_bitrate_max == 1_000_000


def test_parser_event_jsep_extensions_unknown_and_errors() -> None:
    event = parse_recordplay_response(
        {
            "janus": "event",
            "transaction": "tx",
            "plugindata": {
                "plugin": "janus.plugin.recordplay",
                "data": {
                    "recordplay": "event",
                    "result": {
                        "status": "preparing",
                        "id": 42,
                        "server_extension": True,
                    },
                },
            },
            "jsep": {"type": "offer", "sdp": "v=0\r\n"},
        }
    )
    assert isinstance(event.data, RecordPlayEvent)
    assert event.data.result.status == "preparing"
    assert event.data.result.model_extra == {"server_extension": True}
    assert event.jsep is not None and event.jsep.type == "offer"

    unknown = parse_recordplay_response({"recordplay": "metadata", "revision": 2})
    assert isinstance(unknown.data, UnknownRecordPlayResponse)
    assert unknown.data.model_extra == {"revision": 2}

    future_status = parse_recordplay_response(
        {
            "recordplay": "event",
            "result": {"status": "buffering", "percent": 20},
        }
    )
    assert isinstance(future_status.data.result, UnknownRecordPlayResult)
    assert future_status.data.result.model_extra == {"percent": 20}

    with pytest.raises(RecordPlayPluginError) as error:
        parse_recordplay_response(
            {"recordplay": "event", "error_code": 416, "error": "No such recording"}
        )
    assert error.value.code == 416


def test_distribution_metadata() -> None:
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    project = metadata["project"]
    assert project["name"] == "jrtc-rec"
    assert "jrtc>=3.1,<4" in project["dependencies"]
    assert project["entry-points"]["jrtc.plugins"]["recordplay"].endswith(":RecordPlayPlugin")
