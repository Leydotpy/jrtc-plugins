from __future__ import annotations

import asyncio
from typing import Any

import pytest
from jrtc.models.base import Jsep
from jrtc_nosip import ForwardStream, NoSIPPlugin, NoSipPlugin, NoSipProtocolError


class FakeSession:
    id = 30

    def __init__(self) -> None:
        self.calls: list[tuple[Any, float | None, bool]] = []

    async def send(
        self, request: Any, *, timeout: float | None, wait_for_event: bool
    ) -> dict[str, Any]:
        self.calls.append((request, timeout, wait_for_event))
        response: dict[str, Any] = {
            "janus": "event",
            "sender": 300,
            "plugindata": {
                "plugin": "janus.plugin.nosip",
                "data": {"nosip": "event", "result": {"event": "hangingup"}},
            },
        }
        if request.body["request"] == "process":
            response["jsep"] = {
                "type": request.body["type"],
                "sdp": "v=0\r\n",
            }
        return response


def test_alias_direct_construction_and_all_operations_golden_messages() -> None:
    async def scenario() -> FakeSession:
        session = FakeSession()
        plugin = NoSIPPlugin(session=session, plugin_id=300)
        assert isinstance(plugin, NoSipPlugin)
        await plugin.generate(
            Jsep(type="offer", sdp="v=0\r\n"),
            info="outbound",
            srtp="sdes_optional",
        )
        await plugin.process("answer", "v=0\r\n", timeout=3)
        await plugin.recording("start", audio=True, peer_audio=True, filename="call")
        await plugin.keyframe(user=True)
        await plugin.rtp_forward([ForwardStream(type="audio", host="127.0.0.1", port=5004)])
        await plugin.stop_rtp_forward(9)
        await plugin.list_forwarders()
        await plugin.hangup()
        return session

    session = asyncio.run(scenario())
    assert [call[0].body for call in session.calls] == [
        {
            "request": "generate",
            "info": "outbound",
            "srtp": "sdes_optional",
        },
        {"request": "process", "type": "answer", "sdp": "v=0\r\n"},
        {
            "request": "recording",
            "action": "start",
            "audio": True,
            "peer_audio": True,
            "filename": "call",
        },
        {"request": "keyframe", "user": True},
        {
            "request": "rtp_forward",
            "streams": [{"type": "audio", "host": "127.0.0.1", "port": 5004}],
        },
        {"request": "stop_rtp_forward", "stream_id": 9},
        {"request": "listforwarders"},
        {"request": "hangup"},
    ]
    assert session.calls[0][0].jsep.type == "offer"
    assert session.calls[1][0].jsep is None
    assert all(call[2] is True for call in session.calls)
    assert session.calls[1][1] == 3


def test_generate_jsep_direction_and_blank_sdp_are_guarded_before_io() -> None:
    session = FakeSession()
    plugin = NoSipPlugin(session=session, plugin_id=300)
    with pytest.raises(NoSipProtocolError):
        asyncio.run(plugin.generate(Jsep(type="rollback", sdp="v=0\r\n")))
    with pytest.raises(NoSipProtocolError):
        asyncio.run(plugin.generate(Jsep(type="offer", sdp=" ")))
    assert session.calls == []
