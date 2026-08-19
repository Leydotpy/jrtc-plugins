from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from jrtc_sip import (
    CallRequest,
    DtmfInfoRequest,
    ForwardStream,
    RecordingRequest,
    RegisterRequest,
    SipDtmfResult,
    SipIncomingCallResult,
    SipPluginError,
    SipProtocolError,
    SipRegisteredResult,
    StopRtpForwardRequest,
    UnknownSipResult,
    parse_sip_response,
)
from pydantic import ValidationError


def test_registration_uri_auth_and_mode_invariants() -> None:
    account = RegisterRequest(
        username="sip:alice@example.com",
        ha1_secret="0123456789abcdef0123456789abcdef",
        authuser="alice-auth",
        proxy="sip:registrar.example.com:5060",
        outbound_proxy="sips:edge.example.com",
        force_tcp=True,
        register_ttl=600,
        contact_params={"transport": "tcp"},
    )
    assert account.model_dump(exclude_none=True) == {
        "request": "register",
        "force_tcp": True,
        "username": "sip:alice@example.com",
        "ha1_secret": "0123456789abcdef0123456789abcdef",
        "authuser": "alice-auth",
        "proxy": "sip:registrar.example.com:5060",
        "outbound_proxy": "sips:edge.example.com",
        "contact_params": {"transport": "tcp"},
        "register_ttl": 600,
    }
    assert RegisterRequest(type="guest", username="sip:guest@example.com").model_dump(
        exclude_none=True
    ) == {
        "request": "register",
        "type": "guest",
        "username": "sip:guest@example.com",
    }
    assert (
        RegisterRequest(type="helper", username="sip:alice@example.com", master_id=42).master_id
        == 42
    )

    invalid = [
        {"username": "alice@example.com", "secret": "x"},
        {"username": "sip:a@b"},
        {"username": "sip:a@b", "secret": "x", "ha1_secret": "y"},
        {"username": "sip:a@b", "secret": "x", "force_udp": True, "force_tcp": True},
        {"type": "guest", "username": "sip:a@b", "secret": "x"},
        {"type": "guest", "username": "sip:a@b", "send_register": True},
        {"type": "helper", "username": "sip:a@b"},
        {"type": "helper", "username": "sip:a@b", "master_id": "42"},
        {"type": "helper", "username": "sip:a@b", "master_id": True},
    ]
    for values in invalid:
        with pytest.raises(ValidationError):
            RegisterRequest(**values)


def test_call_recording_dtmf_and_forwarder_models_are_strict() -> None:
    call = CallRequest(
        uri="sip:bob@example.com",
        call_id="call-1",
        refer_id=9,
        srtp="sdes_mandatory",
        srtp_profile="AES_CM_128_HMAC_SHA1_80",
        secret="invite-password",
        authuser="guest-auth",
        autoaccept_reinvites=False,
    )
    assert call.model_dump(exclude_none=True) == {
        "request": "call",
        "uri": "sip:bob@example.com",
        "call_id": "call-1",
        "refer_id": 9,
        "srtp": "sdes_mandatory",
        "srtp_profile": "AES_CM_128_HMAC_SHA1_80",
        "secret": "invite-password",
        "authuser": "guest-auth",
        "autoaccept_reinvites": False,
    }
    with pytest.raises(ValidationError):
        CallRequest(uri="sip:bob@example.com", srtp_profile="profile")
    with pytest.raises(ValidationError):
        DtmfInfoRequest(digit="12")
    with pytest.raises(ValidationError):
        RecordingRequest(action="start")

    recording = RecordingRequest(
        action="start", audio=True, peer_video=True, send_peer_pli=True, filename="call"
    )
    assert recording.send_peer_pli is True
    assert RecordingRequest(action="pause", audio=True).action == "pause"
    stream = ForwardStream(
        type="peer_audio",
        host="203.0.113.8",
        port=5004,
        pt=111,
        srtp_suite=80,
        srtp_crypto="base64-key",
    )
    assert stream.port == 5004
    with pytest.raises(ValidationError):
        ForwardStream(type="audio", host="127.0.0.1", port=0)
    assert StopRtpForwardRequest(streams=[1, 2]).streams == [1, 2]
    with pytest.raises(ValidationError):
        StopRtpForwardRequest(streams=[1], stream_id=2)


def test_parser_typed_events_jsep_extensions_and_plugin_errors() -> None:
    incoming = parse_sip_response(
        {
            "janus": "event",
            "transaction": "tx",
            "plugindata": {
                "plugin": "janus.plugin.sip",
                "data": {
                    "sip": "event",
                    "call_id": "call-1",
                    "result": {
                        "event": "incomingcall",
                        "username": "sip:bob@example.com",
                        "callee": "sip:alice@example.com",
                        "replaces": "old-call-id",
                        "new_field": 7,
                    },
                },
            },
            "jsep": {"type": "offer", "sdp": "v=0\r\n"},
        }
    )
    assert isinstance(incoming.data.result, SipIncomingCallResult)
    assert incoming.data.result.replaces == "old-call-id"
    assert incoming.data.result.model_extra == {"new_field": 7}
    assert incoming.jsep is not None and incoming.jsep.type == "offer"

    registered = parse_sip_response(
        {
            "sip": "event",
            "result": {
                "event": "registered",
                "username": "sip:a@b",
                "register_sent": True,
                "master_id": 9,
                "unique_id": "uuid",
            },
        }
    )
    assert isinstance(registered.data.result, SipRegisteredResult)

    unregistered = parse_sip_response(
        {
            "sip": "event",
            "unique_id": "account-uuid",
            "result": {"event": "unregistered", "username": "sip:a@b"},
        }
    )
    assert isinstance(unregistered.data.result, SipRegisteredResult)
    assert unregistered.data.result.register_sent is None
    assert unregistered.data.unique_id == "account-uuid"

    dtmf = parse_sip_response(
        {
            "sip": "event",
            "result": {
                "event": "dtmf",
                "sender": "sip:bob@example.com",
                "signal": "#",
                "duration": 160,
            },
        }
    )
    assert isinstance(dtmf.data.result, SipDtmfResult)

    future = parse_sip_response({"sip": "event", "result": {"event": "parked", "slot": 3}})
    assert isinstance(future.data.result, UnknownSipResult)
    assert future.data.result.model_extra == {"slot": 3}

    with pytest.raises(SipPluginError) as error:
        parse_sip_response({"sip": "event", "error_code": 447, "error": "Wrong state"})
    assert error.value.code == 447

    with pytest.raises(SipProtocolError):
        parse_sip_response(
            {
                "janus": "event",
                "plugindata": {
                    "plugin": "janus.plugin.sip",
                    "data": {
                        "sip": "event",
                        "result": {"event": "infosent"},
                    },
                },
                "jsep": {"type": "answer", "sdp": " "},
            }
        )

    hangup = parse_sip_response(
        {
            "sip": "event",
            "result": {
                "event": "hangup",
                "code": 486,
                "reason": "Busy Here",
                "reason_header_cause": "17",
            },
        }
    )
    assert hangup.data.result.reason_header_cause == "17"

    with pytest.raises(SipProtocolError):
        parse_sip_response(
            {
                "sip": "event",
                "result": {
                    "event": "hangup",
                    "code": 486,
                    "reason": "Busy Here",
                    "reason_header_cause": 17,
                },
            }
        )


def test_distribution_metadata() -> None:
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    project = metadata["project"]
    assert project["name"] == "jrtc-sip"
    assert "jrtc>=3.1,<4" in project["dependencies"]
    assert project["entry-points"]["jrtc.plugins"]["sip"].endswith(":SipPlugin")
