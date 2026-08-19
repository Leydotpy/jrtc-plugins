from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from jrtc_nosip import (
    ForwardersListed,
    ForwardStream,
    Generated,
    GenerateRequest,
    NoSipPluginError,
    ProcessRequest,
    RecordingRequest,
    RtpForwardRequest,
    StopRtpForwardRequest,
    UnknownNoSipResult,
    parse_nosip_response,
)
from pydantic import ValidationError


def test_sdp_conversion_requests_have_exact_wire_shape() -> None:
    assert GenerateRequest(
        info="call-42", srtp="sdes_optional", srtp_profile="AES_CM_128_HMAC_SHA1_80"
    ).model_dump(exclude_none=True) == {
        "request": "generate",
        "info": "call-42",
        "srtp": "sdes_optional",
        "srtp_profile": "AES_CM_128_HMAC_SHA1_80",
    }
    assert ProcessRequest(type="answer", sdp="v=0\r\n").model_dump(exclude_none=True) == {
        "request": "process",
        "type": "answer",
        "sdp": "v=0\r\n",
    }
    with pytest.raises(ValidationError):
        ProcessRequest(type="answer", sdp=" ")
    with pytest.raises(ValidationError):
        GenerateRequest(srtp_profile="profile-without-policy")
    with pytest.raises(ValidationError):
        GenerateRequest(extension=True)  # type: ignore[call-arg]


def test_recording_keyframe_and_forwarder_invariants() -> None:
    assert RecordingRequest(
        action="start", audio=True, peer_video=True, filename="call"
    ).model_dump(exclude_none=True) == {
        "request": "recording",
        "action": "start",
        "audio": True,
        "peer_video": True,
        "filename": "call",
    }
    stream = ForwardStream(
        type="peer_audio",
        host="203.0.113.4",
        port=5004,
        pt=111,
        srtp_suite=80,
        srtp_crypto="base64-key",
    )
    assert RtpForwardRequest(streams=[stream]).model_dump(exclude_none=True) == {
        "request": "rtp_forward",
        "streams": [
            {
                "type": "peer_audio",
                "host": "203.0.113.4",
                "port": 5004,
                "pt": 111,
                "srtp_suite": 80,
                "srtp_crypto": "base64-key",
            }
        ],
    }
    with pytest.raises(ValidationError):
        RecordingRequest(action="start")
    with pytest.raises(ValidationError):
        ForwardStream(type="audio", host="127.0.0.1", port=0)
    with pytest.raises(ValidationError):
        ForwardStream(type="audio", host="127.0.0.1", port=5004, srtp_suite=32)
    for invalid in ("7", True):
        with pytest.raises(ValidationError):
            StopRtpForwardRequest(stream_id=invalid)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        RtpForwardRequest(streams=[])


def test_parser_handles_generated_forwarders_outer_jsep_and_future_events() -> None:
    generated = parse_nosip_response(
        {
            "nosip": "event",
            "result": {
                "event": "generated",
                "type": "offer",
                "sdp": "v=0\r\n",
                "unique_id": "8a16",
                "server_field": 1,
            },
        }
    )
    assert isinstance(generated.data.result, Generated)
    assert generated.data.result.model_extra == {"server_field": 1}

    listed = parse_nosip_response(
        {
            "janus": "event",
            "plugindata": {
                "plugin": "janus.plugin.nosip",
                "data": {
                    "nosip": "event",
                    "result": {
                        "event": "forwarders",
                        "forwarders": [
                            {
                                "stream_id": 7,
                                "type": "audio",
                                "host": "127.0.0.1",
                                "port": 5004,
                                "media": "audio",
                            }
                        ],
                    },
                },
            },
            "jsep": {"type": "answer", "sdp": "v=0\r\n"},
        }
    )
    assert isinstance(listed.data.result, ForwardersListed)
    assert listed.data.result.forwarders[0].stream_id == 7
    assert listed.jsep is not None and listed.jsep.type == "answer"

    future = parse_nosip_response({"nosip": "event", "result": {"event": "rekeyed", "epoch": 2}})
    assert isinstance(future.data.result, UnknownNoSipResult)
    assert future.data.result.model_extra == {"epoch": 2}


def test_parser_raises_plugin_error() -> None:
    with pytest.raises(NoSipPluginError) as error:
        parse_nosip_response({"nosip": "event", "error_code": 448, "error": "Wrong state"})
    assert error.value.code == 448


def test_distribution_metadata() -> None:
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    project = metadata["project"]
    assert project["name"] == "jrtc-nosip"
    assert "jrtc>=3.1,<4" in project["dependencies"]
    assert project["entry-points"]["jrtc.plugins"]["nosip"].endswith(":NoSipPlugin")
