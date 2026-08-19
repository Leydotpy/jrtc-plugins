from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from typing import Any

import pytest
from jrtc.models.base import Jsep
from jrtc_text import (
    ControlOk,
    CreatedResponse,
    SuccessResponse,
    TextRoomPlugin,
    TextRoomProtocolError,
    TextRoomResponse,
)


class FakeSession:
    id = 50

    def __init__(self) -> None:
        self.calls: list[tuple[Any, float | None, bool]] = []

    async def send(
        self, request: Any, *, timeout: float | None, wait_for_event: bool
    ) -> dict[str, Any]:
        self.calls.append((request, timeout, wait_for_event))
        operation = request.body["request"]
        data: dict[str, Any]
        jsep: dict[str, Any] | None = None
        if operation in {"setup", "restart", "ack"}:
            data = {"textroom": "event", "result": "ok"}
            if operation != "ack":
                jsep = {"type": "offer", "sdp": "v=0\r\n"}
                if operation == "restart":
                    jsep["restart"] = True
        elif operation == "create":
            data = {
                "textroom": "created",
                "room": request.body.get("room", 1234),
                "permanent": request.body.get("permanent", False),
            }
        elif operation == "edit":
            data = {
                "textroom": "edited",
                "room": request.body["room"],
                "permanent": request.body.get("permanent", False),
            }
        elif operation == "destroy":
            data = {
                "textroom": "destroyed",
                "room": request.body["room"],
                "permanent": request.body.get("permanent", False),
            }
        else:
            data = {"textroom": "success"}
            if "room" in request.body:
                data["room"] = request.body["room"]
            if operation == "exists":
                data["exists"] = True
            if operation == "list":
                data["list"] = []
            if operation == "listparticipants":
                data["participants"] = []
            if operation == "allowed" and request.body["action"] != "disable":
                data["allowed"] = request.body.get("allowed", [])
        response: dict[str, Any] = {
            "janus": "event",
            "transaction": "janus-tx",
            "plugindata": {
                "plugin": "janus.plugin.textroom",
                "data": data,
            },
        }
        if jsep is not None:
            response["jsep"] = jsep
        return response


class FakeChannel:
    ready_state = "open"

    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, data: str) -> None:
        self.sent.append(data)


async def _complete_data_request(
    plugin: TextRoomPlugin,
    channel: FakeChannel,
    operation: Awaitable[TextRoomResponse],
) -> tuple[TextRoomResponse, dict[str, Any]]:
    task = asyncio.ensure_future(operation)
    await asyncio.sleep(0)
    outbound = json.loads(channel.sent[-1])
    plugin.feed_datachannel(
        json.dumps(
            {
                "textroom": "success",
                "transaction": outbound["transaction"],
            }
        )
    )
    return await task, outbound


def test_control_and_admin_operations_use_the_correct_janus_semantics() -> None:
    async def scenario() -> FakeSession:
        session = FakeSession()
        plugin = TextRoomPlugin(session=session, plugin_id=500)
        setup = await plugin.setup()
        restart = await plugin.restart()
        ack = await plugin.ack(Jsep(type="answer", sdp="v=0\r\n"))
        listed = await plugin.list_rooms(admin_key="admin")
        participants = await plugin.list_participants(1234)
        created = await plugin.create_room(
            room=1234,
            description="Support",
            history=25,
            allowed=["agent"],
            permanent=True,
        )
        await plugin.edit_room(1234, new_post="https://example.test/messages")
        await plugin.room_exists(1234)
        await plugin.allowed(1234, "add", tokens=["customer"])
        await plugin.destroy_room(1234, permanent=True)

        assert isinstance(setup.data, ControlOk)
        assert setup.jsep is not None and setup.jsep.type == "offer"
        assert restart.jsep is not None and restart.jsep.restart is True
        assert ack.jsep is None
        assert isinstance(listed.data, SuccessResponse)
        assert isinstance(participants.data, SuccessResponse)
        assert isinstance(created.data, CreatedResponse)
        return session

    session = asyncio.run(scenario())
    bodies = [call[0].body for call in session.calls]
    assert [body["request"] for body in bodies] == [
        "setup",
        "restart",
        "ack",
        "list",
        "listparticipants",
        "create",
        "edit",
        "exists",
        "allowed",
        "destroy",
    ]
    assert all("textroom" not in body for body in bodies)
    assert all("transaction" not in body for body in bodies)
    assert [call[2] for call in session.calls] == [True, True, True] + [False] * 7
    assert session.calls[2][0].jsep.type == "answer"
    assert bodies[5] == {
        "request": "create",
        "room": 1234,
        "description": "Support",
        "history": 25,
        "allowed": ["agent"],
        "permanent": True,
    }
    assert bodies[6]["new_post"] == "https://example.test/messages"


def test_participation_uses_only_the_datachannel_surface() -> None:
    async def scenario() -> tuple[FakeSession, FakeChannel, list[dict[str, Any]]]:
        session = FakeSession()
        channel = FakeChannel()
        plugin = TextRoomPlugin(session=session, plugin_id=500)
        manager = plugin.bind_datachannel(channel)

        responses_and_messages = [
            await _complete_data_request(
                plugin,
                channel,
                plugin.join(
                    1234,
                    "alice",
                    display="Alice",
                    transaction="join-tx",
                ),
            ),
            await _complete_data_request(
                plugin,
                channel,
                plugin.announcement(1234, "Maintenance", secret="room-secret"),
            ),
            await _complete_data_request(
                plugin,
                channel,
                plugin.kick(1234, "bob", secret="room-secret"),
            ),
            await _complete_data_request(
                plugin,
                channel,
                plugin.leave(1234, transaction="leave-tx"),
            ),
        ]
        no_ack = await plugin.message(
            1234, "hello", to="bob", ack=False, transaction="message-tx"
        )
        assert no_ack is None
        assert manager.pending_count == 0
        return session, channel, [item[1] for item in responses_and_messages]

    session, channel, outbound = asyncio.run(scenario())
    assert session.calls == []
    assert [message["textroom"] for message in outbound] == [
        "join",
        "announcement",
        "kick",
        "leave",
    ]
    assert outbound[0]["transaction"] == "join-tx"
    assert outbound[-1]["transaction"] == "leave-tx"
    assert all("request" not in message for message in outbound)
    no_ack = json.loads(channel.sent[-1])
    assert no_ack == {
        "textroom": "message",
        "transaction": "message-tx",
        "room": 1234,
        "text": "hello",
        "to": "bob",
        "ack": False,
    }


def test_jsep_guards_fail_before_network_io() -> None:
    session = FakeSession()
    plugin = TextRoomPlugin(session=session, plugin_id=500)
    with pytest.raises(TextRoomProtocolError):
        asyncio.run(plugin.ack(Jsep(type="offer", sdp="v=0\r\n")))
    blank = Jsep.model_construct(type="answer", sdp=" ")
    with pytest.raises(TextRoomProtocolError):
        asyncio.run(plugin.ack(blank))
    assert session.calls == []
