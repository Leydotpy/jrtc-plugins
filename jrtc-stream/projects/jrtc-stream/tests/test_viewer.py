from __future__ import annotations

import pytest

from janus_streaming import SessionDescription, StreamingViewer, ViewerState

from .fakes import FakeHandle, event_response


@pytest.mark.asyncio
async def test_viewer_state_machine(monkeypatch):
    handle = FakeHandle(
        [
            event_response(
                {"status": "preparing"},
                jsep={"type": "offer", "sdp": "v=0\r\n"},
            ),
            event_response({"status": "starting"}),
            event_response({"status": "pausing"}),
            event_response({"status": "starting"}),
        ]
    )

    async def factory(*args, **kwargs):
        return handle

    viewer = StreamingViewer(object(), mountpoint_id=10, handle_factory=factory)
    offer = await viewer.prepare()
    assert offer.type == "offer"
    assert viewer.state is ViewerState.OFFERED
    await viewer.accept_answer(SessionDescription(type="answer", sdp="v=0\r\n"))
    assert viewer.state is ViewerState.ACTIVE
    await viewer.pause()
    assert viewer.state is ViewerState.PAUSED
    await viewer.resume()
    assert viewer.state is ViewerState.ACTIVE
    await viewer.close()
    assert viewer.state is ViewerState.CLOSED
    assert handle.closed is True
