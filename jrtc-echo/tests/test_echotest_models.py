from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from jrtc_echo import (
    EchoTestDone,
    EchoTestJanusError,
    EchoTestOk,
    EchoTestPluginError,
    EchoTestRequest,
    UnknownEchoTestResponse,
    parse_echotest_response,
)
from pydantic import ValidationError


def test_request_golden_wire_shape_and_strictness() -> None:
    request = EchoTestRequest(
        audio=True,
        video=False,
        bitrate=1_500_000,
        record=True,
        filename="capture",
        substream=2,
        temporal=1,
        svc=True,
        spatial_layer=1,
        temporal_layer=2,
    )
    assert request.model_dump(exclude_none=True, exclude_unset=True) == {
        "audio": True,
        "video": False,
        "bitrate": 1_500_000,
        "record": True,
        "filename": "capture",
        "substream": 2,
        "temporal": 1,
        "svc": True,
        "spatial_layer": 1,
        "temporal_layer": 2,
    }
    with pytest.raises(ValidationError):
        EchoTestRequest(unknown=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        EchoTestRequest(substream=3)
    with pytest.raises(ValidationError):
        EchoTestRequest(spatial_layer=3)


def test_parser_known_events_jsep_and_future_fields() -> None:
    reply = parse_echotest_response(
        {
            "janus": "event",
            "transaction": "tx-1",
            "plugindata": {
                "plugin": "janus.plugin.echotest",
                "data": {"echotest": "event", "result": "ok", "new_metric": 7},
            },
            "jsep": {"type": "answer", "sdp": "v=0\r\n", "server_hint": True},
        }
    )
    assert isinstance(reply.data, EchoTestOk)
    assert reply.data.model_extra == {"new_metric": 7}
    assert reply.jsep is not None and reply.jsep.type == "answer"
    assert reply.jsep.model_extra == {"server_hint": True}
    assert reply.transaction == "tx-1"
    assert isinstance(
        parse_echotest_response({"echotest": "event", "result": "done"}).data,
        EchoTestDone,
    )


def test_parser_preserves_unknown_variants_and_raises_typed_errors() -> None:
    future = parse_echotest_response(
        {"echotest": "future", "result": {"status": "new"}, "extension": 1}
    )
    assert isinstance(future.data, UnknownEchoTestResponse)
    assert future.data.model_extra == {"extension": 1}

    with pytest.raises(EchoTestPluginError) as plugin_error:
        parse_echotest_response(
            {"echotest": "event", "error_code": 411, "error": "No WebRTC media"}
        )
    assert plugin_error.value.code == 411

    with pytest.raises(EchoTestJanusError) as janus_error:
        parse_echotest_response(
            {
                "janus": "error",
                "transaction": "bad-tx",
                "error": {"code": 458, "reason": "Session not found"},
            }
        )
    assert janus_error.value.transaction == "bad-tx"


def test_distribution_metadata() -> None:
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    project = metadata["project"]
    assert project["name"] == "jrtc-echo"
    assert "jrtc>=3.1,<4" in project["dependencies"]
    assert project["entry-points"]["jrtc.plugins"]["echotest"].endswith(":EchoTestPlugin")
