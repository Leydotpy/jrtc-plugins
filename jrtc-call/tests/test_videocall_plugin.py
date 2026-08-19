from __future__ import annotations

import asyncio
from typing import Any

import pytest
from jrtc.models.base import Jsep
from jrtc_call import VideoCallPlugin, VideoCallProtocolError


class FakeSession:
    id = 20

    def __init__(self) -> None:
        self.calls: list[tuple[Any, float | None, bool]] = []

    async def send(
        self, request: Any, *, timeout: float | None, wait_for_event: bool
    ) -> dict[str, Any]:
        self.calls.append((request, timeout, wait_for_event))
        return {
            "janus": "event",
            "sender": 200,
            "plugindata": {
                "plugin": "janus.plugin.videocall",
                "data": {"videocall": "event", "result": {"event": "set"}},
            },
        }


def test_all_documented_operations_have_golden_outer_messages() -> None:
    async def scenario() -> FakeSession:
        session = FakeSession()
        plugin = VideoCallPlugin(session=session, plugin_id=200)
        await plugin.list_peers(timeout=1)
        await plugin.register("alice")
        await plugin.call("bob", Jsep(type="offer", sdp="v=0\r\n"))
        await plugin.accept(Jsep(type="answer", sdp="v=0\r\n"))
        await plugin.set(audio=False, bitrate=256_000, substream=1)
        await plugin.hangup()
        return session

    session = asyncio.run(scenario())
    assert [call[0].body for call in session.calls] == [
        {"request": "list"},
        {"request": "register", "username": "alice"},
        {"request": "call", "username": "bob"},
        {"request": "accept"},
        {"request": "set", "audio": False, "bitrate": 256_000, "substream": 1},
        {"request": "hangup"},
    ]
    assert session.calls[2][0].jsep.type == "offer"
    assert session.calls[3][0].jsep.type == "answer"
    assert all(call[2] is True for call in session.calls)
    assert session.calls[0][1] == 1


def test_jsep_direction_guards_run_before_io() -> None:
    session = FakeSession()
    plugin = VideoCallPlugin(session=session, plugin_id=200)
    with pytest.raises(VideoCallProtocolError):
        asyncio.run(plugin.call("bob", Jsep(type="answer", sdp="v=0\r\n")))
    with pytest.raises(VideoCallProtocolError):
        asyncio.run(plugin.accept(Jsep(type="offer", sdp="v=0\r\n")))
    with pytest.raises(VideoCallProtocolError):
        asyncio.run(plugin.set(jsep=Jsep(type="rollback", sdp="v=0\r\n")))
    with pytest.raises(VideoCallProtocolError):
        asyncio.run(plugin.set())
    assert session.calls == []


def test_set_supports_renegotiation_offer_or_answer() -> None:
    async def scenario() -> FakeSession:
        session = FakeSession()
        plugin = VideoCallPlugin(session=session, plugin_id=200)
        await plugin.set(video=True, jsep=Jsep(type="offer", sdp="v=0\r\n"))
        await plugin.set(video=True, jsep=Jsep(type="answer", sdp="v=0\r\n"))
        return session

    session = asyncio.run(scenario())
    assert [call[0].jsep.type for call in session.calls] == ["offer", "answer"]
