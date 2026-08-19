from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from jrtc_text import (
    AllowedRequest,
    ChatMessageRequest,
    CreatedResponse,
    CreateRoomRequest,
    EditRoomRequest,
    JoinRequest,
    MessageEvent,
    SetupRequest,
    SuccessResponse,
    TextRoomJanusError,
    TextRoomPluginError,
    TextRoomProtocolError,
    UnknownTextRoomResponse,
    parse_textroom_data_response,
    parse_textroom_janus_response,
)
from pydantic import ValidationError


def test_janus_and_datachannel_models_have_distinct_wire_discriminators() -> None:
    setup = SetupRequest()
    assert setup.model_dump(exclude_none=True) == {"request": "setup"}

    create = CreateRoomRequest(
        room=1234,
        admin_key="admin",
        description="Support",
        history=25,
        allowed=["customer", "agent"],
        permanent=True,
    )
    assert create.model_dump(exclude_none=True) == {
        "request": "create",
        "room": 1234,
        "admin_key": "admin",
        "description": "Support",
        "history": 25,
        "allowed": ["customer", "agent"],
        "permanent": True,
    }
    assert "textroom" not in create.model_dump()
    assert "transaction" not in create.model_dump()

    join = JoinRequest(
        room=1234,
        username="alice",
        display="Alice",
        transaction="join-1",
    )
    assert join.model_dump(exclude_none=True) == {
        "textroom": "join",
        "transaction": "join-1",
        "room": 1234,
        "username": "alice",
        "display": "Alice",
    }
    assert "request" not in join.model_dump()


def test_room_admin_and_message_invariants_are_validated_locally() -> None:
    assert EditRoomRequest(room=99, new_post="https://example.test/messages").new_post
    assert AllowedRequest(room=99, action="add", allowed=["token"]).allowed == ["token"]
    assert ChatMessageRequest(room=99, text="hello", ack=False).ack is False

    invalid_factories = (
        lambda: CreateRoomRequest(room=True),
        lambda: CreateRoomRequest(room=0),
        lambda: CreateRoomRequest(room="1234"),
        lambda: CreateRoomRequest(room="support"),
        lambda: CreateRoomRequest(history=0),
        lambda: EditRoomRequest(room=99),
        lambda: AllowedRequest(room=99, action="add"),
        lambda: AllowedRequest(room=99, action="enable", allowed=["token"]),
        lambda: ChatMessageRequest(room=99, text="hello", to="a", tos=["b"]),
        lambda: JoinRequest(room=99, username="alice", unexpected=True),
    )
    for factory in invalid_factories:
        with pytest.raises(ValidationError):
            factory()


def test_data_response_parser_is_typed_and_forward_compatible() -> None:
    success = parse_textroom_data_response(
        {
            "textroom": "success",
            "transaction": "tx-1",
            "participants": [{"username": "bob", "display": "Bob"}],
        }
    )
    assert isinstance(success, SuccessResponse)
    assert success.participants is not None
    assert success.participants[0].username == "bob"

    message = parse_textroom_data_response(
        {
            "textroom": "message",
            "room": 1234,
            "from": "bob",
            "date": "2026-07-12T10:00:00+0100",
            "text": "hello",
            "future_field": 7,
        }
    )
    assert isinstance(message, MessageEvent)
    assert message.from_ == "bob"
    assert message.model_extra == {"future_field": 7}

    unknown = parse_textroom_data_response(
        {"textroom": "moderated", "transaction": "tx-2", "state": True}
    )
    assert isinstance(unknown, UnknownTextRoomResponse)
    assert unknown.model_extra == {"state": True}

    with pytest.raises(TextRoomPluginError) as error:
        parse_textroom_data_response(
            {
                "textroom": "error",
                "transaction": "tx-3",
                "error_code": 417,
                "error": "No such room",
            }
        )
    assert error.value.code == 417
    assert error.value.transaction == "tx-3"


def test_janus_response_parser_preserves_outer_jsep_and_errors() -> None:
    reply = parse_textroom_janus_response(
        {
            "janus": "success",
            "transaction": "janus-tx",
            "plugindata": {
                "plugin": "janus.plugin.textroom",
                "data": {
                    "textroom": "created",
                    "room": 1234,
                    "permanent": True,
                },
            },
        }
    )
    assert isinstance(reply.data, CreatedResponse)
    assert reply.transaction == "janus-tx"

    offer = parse_textroom_janus_response(
        {
            "janus": "event",
            "plugindata": {
                "plugin": "janus.plugin.textroom",
                "data": {"textroom": "event", "result": "ok"},
            },
            "jsep": {"type": "offer", "sdp": "v=0\r\n", "restart": True},
        }
    )
    assert offer.jsep is not None and offer.jsep.restart is True

    with pytest.raises(TextRoomProtocolError):
        parse_textroom_janus_response(
            {
                "janus": "event",
                "plugindata": {
                    "plugin": "janus.plugin.textroom",
                    "data": {"textroom": "event", "result": "ok"},
                },
                "jsep": {"type": "offer", "sdp": " "},
            }
        )

    with pytest.raises(TextRoomJanusError) as error:
        parse_textroom_janus_response(
            {
                "janus": "error",
                "transaction": "janus-failed",
                "error": {"code": 458, "reason": "session not found"},
            }
        )
    assert error.value.transaction == "janus-failed"

    with pytest.raises(TextRoomProtocolError):
        parse_textroom_janus_response(
            {
                "janus": "event",
                "plugindata": {
                    "plugin": "janus.plugin.videoroom",
                    "data": {"textroom": "success"},
                },
            }
        )


def test_distribution_metadata() -> None:
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    project = metadata["project"]
    assert project["name"] == "jrtc-text"
    assert "jrtc>=3.1,<4" in project["dependencies"]
    entry = project["entry-points"]["jrtc.plugins"]["textroom"]
    assert entry == "janus_textroom_plugin:TextRoomPlugin"
