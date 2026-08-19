from __future__ import annotations

import asyncio
from typing import Any

import pytest
from jrtc.models.base import Jsep
from jrtc_echo import (
    EchoTestOk,
    EchoTestPlugin,
    EchoTestProtocolError,
    EchoTestRequest,
)


class FakeSession:
    id = 10

    def __init__(self) -> None:
        self.calls: list[tuple[Any, float | None, bool]] = []
        self.response: dict[str, Any] = {
            "janus": "event",
            "transaction": "tx",
            "sender": 99,
            "plugindata": {
                "plugin": "janus.plugin.echotest",
                "data": {"echotest": "event", "result": "ok"},
            },
        }

    async def send(
        self, request: Any, *, timeout: float | None, wait_for_event: bool
    ) -> dict[str, Any]:
        self.calls.append((request, timeout, wait_for_event))
        return self.response


def test_direct_construction_and_configure_golden_envelope() -> None:
    session = FakeSession()
    plugin = EchoTestPlugin(session=session, plugin_id=99)
    reply = asyncio.run(plugin.configure(audio=True, video=False, bitrate=512_000, timeout=2.5))
    request, timeout, wait = session.calls[-1]
    assert plugin.identifier == "echotest"
    assert plugin.name == "janus.plugin.echotest"
    assert request.body == {"audio": True, "video": False, "bitrate": 512_000}
    assert request.jsep is None
    assert request.session_id == 10 and request.handle_id == 99
    assert (timeout, wait) == (2.5, True)
    assert isinstance(reply.data, EchoTestOk)


def test_negotiation_requires_offer_and_returns_outer_answer() -> None:
    session = FakeSession()
    session.response["jsep"] = {"type": "answer", "sdp": "v=0\r\n"}
    plugin = EchoTestPlugin(session=session, plugin_id=99)
    reply = asyncio.run(
        plugin.negotiate(
            Jsep(type="offer", sdp="v=0\r\n"),
            settings=EchoTestRequest(audio=True, videocodec="vp8"),
        )
    )
    request = session.calls[-1][0]
    assert request.body == {"audio": True, "videocodec": "vp8"}
    assert request.jsep.type == "offer"
    assert reply.jsep is not None and reply.jsep.type == "answer"

    with pytest.raises(EchoTestProtocolError):
        asyncio.run(plugin.negotiate(Jsep(type="answer", sdp="v=0\r\n")))
    with pytest.raises(EchoTestProtocolError):
        asyncio.run(plugin.negotiate(Jsep(type="offer", sdp="   ")))
