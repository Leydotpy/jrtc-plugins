from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from jrtc_call import (
    IncomingCall,
    PeerList,
    RegisterRequest,
    SetRequest,
    UnknownVideoCallResult,
    VideoCallJanusError,
    VideoCallPluginError,
    parse_videocall_response,
)
from pydantic import ValidationError


def test_requests_are_strict_and_serialize_to_documented_wire_shape() -> None:
    assert RegisterRequest(username=" alice ").model_dump(exclude_none=True) == {
        "request": "register",
        "username": "alice",
    }
    assert SetRequest(
        audio=False,
        video=True,
        bitrate=0,
        substream=2,
        temporal=1,
        fallback=3_000,
    ).model_dump(exclude_none=True) == {
        "request": "set",
        "audio": False,
        "video": True,
        "bitrate": 0,
        "substream": 2,
        "temporal": 1,
        "fallback": 3_000,
    }
    with pytest.raises(ValidationError):
        RegisterRequest(username=" ")
    with pytest.raises(ValidationError):
        SetRequest(substream=8)
    with pytest.raises(ValidationError):
        SetRequest(typo=True)  # type: ignore[call-arg]


def test_parser_handles_list_signalling_events_jsep_and_extensions() -> None:
    listed = parse_videocall_response(
        {"videocall": "event", "result": {"list": ["alice", "bob"], "count": 2}}
    )
    assert isinstance(listed.data.result, PeerList)
    assert listed.data.result.peers == ["alice", "bob"]
    assert listed.data.result.model_extra == {"count": 2}

    incoming = parse_videocall_response(
        {
            "janus": "event",
            "transaction": "tx",
            "plugindata": {
                "plugin": "janus.plugin.videocall",
                "data": {
                    "videocall": "event",
                    "result": {"event": "incomingcall", "username": "alice"},
                },
            },
            "jsep": {"type": "offer", "sdp": "v=0\r\n"},
        }
    )
    assert isinstance(incoming.data.result, IncomingCall)
    assert incoming.jsep is not None and incoming.jsep.type == "offer"

    future = parse_videocall_response(
        {
            "videocall": "event",
            "result": {"event": "transferred", "target": "carol"},
        }
    )
    assert isinstance(future.data.result, UnknownVideoCallResult)
    assert future.data.result.model_extra == {"target": "carol"}


def test_parser_raises_typed_errors() -> None:
    with pytest.raises(VideoCallPluginError) as error:
        parse_videocall_response(
            {"videocall": "event", "error_code": 478, "error": "Username taken"}
        )
    assert error.value.code == 478
    with pytest.raises(VideoCallJanusError):
        parse_videocall_response(
            {"janus": "error", "error": {"code": 459, "reason": "Handle not found"}}
        )


def test_distribution_metadata() -> None:
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    project = metadata["project"]
    assert project["name"] == "jrtc-call"
    assert "jrtc>=3.1,<4" in project["dependencies"]
    assert project["entry-points"]["jrtc.plugins"]["videocall"].endswith(":VideoCallPlugin")
