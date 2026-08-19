from __future__ import annotations

import asyncio
from typing import Any

import pytest
from jrtc.models.base import Jsep
from jrtc_sip import ForwardStream, SIPPlugin, SipPlugin, SipProtocolError


class FakeSession:
    id = 50

    def __init__(self) -> None:
        self.calls: list[tuple[Any, float | None, bool]] = []

    async def send(
        self, request: Any, *, timeout: float | None, wait_for_event: bool
    ) -> dict[str, Any]:
        self.calls.append((request, timeout, wait_for_event))
        return {
            "janus": "event",
            "sender": 500,
            "plugindata": {
                "plugin": "janus.plugin.sip",
                "data": {"sip": "event", "result": {"event": "infosent"}},
            },
        }


def test_every_documented_operation_uses_async_plugin_messages() -> None:
    async def scenario() -> FakeSession:
        session = FakeSession()
        plugin = SIPPlugin(session=session, plugin_id=500)
        assert isinstance(plugin, SipPlugin)
        await plugin.register(
            "sip:alice@example.com",
            secret="password",
            proxy="sip:registrar.example.com",
            force_tcp=True,
        )
        await plugin.register_guest("sip:guest@example.com")
        await plugin.register_helper("sip:alice@example.com", 77)
        await plugin.unregister()
        await plugin.call(
            "sip:bob@example.com",
            Jsep(type="offer", sdp="v=0\r\n"),
            srtp="sdes_optional",
        )
        await plugin.progress(Jsep(type="answer", sdp="v=0\r\n"))
        await plugin.accept(Jsep(type="offer", sdp="v=0\r\n"), autoaccept_reinvites=False)
        await plugin.update(Jsep(type="answer", sdp="v=0\r\n"))
        await plugin.decline(code=486, refer_id=3)
        await plugin.hold("inactive")
        await plugin.unhold()
        await plugin.message("hello", content_type="text/plain", uri="sip:bob@example.com")
        await plugin.info("application/test", "payload")
        await plugin.dtmf_info("#", duration=250)
        await plugin.subscribe("message-summary", to="sip:alice@example.com")
        await plugin.unsubscribe("message-summary")
        await plugin.transfer("sip:carol@example.com", replace="call-2")
        await plugin.recording(
            "start", audio=True, peer_audio=True, send_peer_pli=True, filename="call"
        )
        await plugin.keyframe(user=True, peer=True)
        await plugin.rtp_forward(
            [ForwardStream(type="audio", host="127.0.0.1", port=5004)],
            unique_id="account-uuid",
            admin_key="forward-secret",
        )
        await plugin.stop_rtp_forward(
            [10, 11], unique_id="account-uuid", admin_key="forward-secret"
        )
        await plugin.list_forwarders(unique_id="account-uuid", admin_key="forward-secret")
        await plugin.hangup(headers={"X-Reason": "done"}, timeout=4)
        return session

    session = asyncio.run(scenario())
    bodies = [call[0].body for call in session.calls]
    assert [body["request"] for body in bodies] == [
        "register",
        "register",
        "register",
        "unregister",
        "call",
        "progress",
        "accept",
        "update",
        "decline",
        "hold",
        "unhold",
        "message",
        "info",
        "dtmf_info",
        "subscribe",
        "unsubscribe",
        "transfer",
        "recording",
        "keyframe",
        "rtp_forward",
        "stop_rtp_forward",
        "listforwarders",
        "hangup",
    ]
    assert bodies[0] == {
        "request": "register",
        "force_tcp": True,
        "username": "sip:alice@example.com",
        "secret": "password",
        "proxy": "sip:registrar.example.com",
    }
    assert bodies[1] == {
        "request": "register",
        "type": "guest",
        "username": "sip:guest@example.com",
    }
    assert bodies[2]["master_id"] == 77
    assert bodies[4]["uri"] == "sip:bob@example.com"
    assert bodies[6]["autoaccept_reinvites"] is False
    assert bodies[17]["send_peer_pli"] is True
    assert bodies[19]["unique_id"] == "account-uuid"
    assert bodies[19]["admin_key"] == "forward-secret"
    assert bodies[20] == {
        "request": "stop_rtp_forward",
        "unique_id": "account-uuid",
        "admin_key": "forward-secret",
        "streams": [10, 11],
    }
    assert bodies[21]["unique_id"] == "account-uuid"
    assert session.calls[4][0].jsep.type == "offer"
    assert session.calls[5][0].jsep.type == "answer"
    assert session.calls[6][0].jsep.type == "offer"
    assert session.calls[7][0].jsep.type == "answer"
    assert session.calls[7][0].jsep.model_extra == {"update": True}
    assert all(call[2] is True for call in session.calls)
    assert session.calls[-1][1] == 4


def test_jsep_guards_prevent_invalid_io() -> None:
    session = FakeSession()
    plugin = SipPlugin(session=session, plugin_id=500)
    with pytest.raises(SipProtocolError):
        asyncio.run(plugin.call("sip:bob@example.com", Jsep(type="answer", sdp="v=0\r\n")))
    with pytest.raises(SipProtocolError):
        asyncio.run(plugin.accept(Jsep(type="rollback", sdp="v=0\r\n")))
    # Bypass core construction so this test remains focused on the plugin's
    # defensive boundary even when core also rejects blank SDP.
    blank = Jsep.model_construct(type="offer", sdp=" ")
    with pytest.raises(SipProtocolError):
        asyncio.run(plugin.update(blank))
    assert session.calls == []
