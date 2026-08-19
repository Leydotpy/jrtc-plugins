from __future__ import annotations

import asyncio
from typing import Any

import pytest
from jrtc.models.base import Jsep
from jrtc_rec import RecordPlayPlugin, RecordPlayProtocolError


class FakeSession:
    id = 40

    def __init__(self) -> None:
        self.calls: list[tuple[Any, float | None, bool]] = []

    async def send(
        self, request: Any, *, timeout: float | None, wait_for_event: bool
    ) -> dict[str, Any]:
        self.calls.append((request, timeout, wait_for_event))
        if not wait_for_event:
            body_type = request.body["request"]
            if body_type == "list":
                data: dict[str, Any] = {"recordplay": "list", "list": []}
            elif body_type == "update":
                data = {"recordplay": "ok"}
            else:
                data = {
                    "recordplay": "configure",
                    "status": "ok",
                    "settings": {
                        "video-bitrate-max": request.body.get("video-bitrate-max"),
                        "video-keyframe-interval": request.body.get("video-keyframe-interval"),
                    },
                }
        else:
            data = {"recordplay": "event", "result": {"status": "stopped"}}
        response: dict[str, Any] = {
            "janus": "event" if wait_for_event else "success",
            "sender": 400,
            "plugindata": {"plugin": "janus.plugin.recordplay", "data": data},
        }
        if request.body["request"] == "record":
            response["jsep"] = {"type": "answer", "sdp": "v=0\r\n"}
        elif request.body["request"] == "play":
            response["jsep"] = {"type": "offer", "sdp": "v=0\r\n"}
        return response


def test_all_operations_exact_body_and_sync_async_split() -> None:
    async def scenario() -> FakeSession:
        session = FakeSession()
        plugin = RecordPlayPlugin(session=session, plugin_id=400)
        await plugin.list_recordings(admin_key="secret", timeout=1)
        await plugin.update(admin_key="secret")
        await plugin.configure(video_bitrate_max=800_000, video_keyframe_interval=4)
        await plugin.record(
            "demo",
            Jsep(type="offer", sdp="v=0\r\n"),
            recording_id=55,
            is_private=True,
            opusred=True,
            textdata=False,
        )
        await plugin.play(55, restart=True)
        await plugin.start(Jsep(type="answer", sdp="v=0\r\n"))
        await plugin.pause()
        await plugin.resume()
        await plugin.stop()
        return session

    session = asyncio.run(scenario())
    assert [call[0].body for call in session.calls] == [
        {"request": "list", "admin_key": "secret"},
        {"request": "update", "admin_key": "secret"},
        {
            "request": "configure",
            "video-bitrate-max": 800_000,
            "video-keyframe-interval": 4,
        },
        {
            "request": "record",
            "id": 55,
            "name": "demo",
            "is_private": True,
            "opusred": True,
            "textdata": False,
        },
        {"request": "play", "id": 55, "restart": True},
        {"request": "start"},
        {"request": "pause"},
        {"request": "resume"},
        {"request": "stop"},
    ]
    assert [call[2] for call in session.calls] == [
        False,
        False,
        False,
        True,
        True,
        True,
        True,
        True,
        True,
    ]
    assert session.calls[3][0].jsep.type == "offer"
    assert session.calls[4][0].jsep is None  # play must let Janus originate the offer
    assert session.calls[5][0].jsep.type == "answer"
    assert session.calls[0][1] == 1


def test_record_and_start_enforce_opposite_jsep_directions_before_io() -> None:
    session = FakeSession()
    plugin = RecordPlayPlugin(session=session, plugin_id=400)
    with pytest.raises(RecordPlayProtocolError):
        asyncio.run(plugin.record("demo", Jsep(type="answer", sdp="v=0\r\n")))
    with pytest.raises(RecordPlayProtocolError):
        asyncio.run(plugin.start(Jsep(type="offer", sdp="v=0\r\n")))
    with pytest.raises(RecordPlayProtocolError):
        asyncio.run(plugin.start(Jsep(type="answer", sdp=" ")))
    assert session.calls == []
