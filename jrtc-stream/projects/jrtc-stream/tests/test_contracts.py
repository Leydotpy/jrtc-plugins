from __future__ import annotations

from types import SimpleNamespace

import pytest

from janus_streaming import (
    IceCandidate,
    InvalidViewerState,
    JanusCommandError,
    RtspMountpointSpec,
    SessionDescription,
    StreamingAdminClient,
    StreamingViewer,
    _compat,
)

from .fakes import FakeHandle, event_response


def dumped(value):
    return value.model_dump(mode="json", by_alias=True, exclude_none=True)


@pytest.mark.asyncio
async def test_rtsp_request_maps_all_upstream_field_names() -> None:
    handle = FakeHandle(
        [
            event_response(
                {
                    "create": "created",
                    "permanent": True,
                    "stream": {"id": 44, "type": "rtsp", "description": "camera"},
                }
            )
        ]
    )

    async def factory(*args, **kwargs):
        return handle

    client = StreamingAdminClient(
        object(),
        admin_key="admin-secret",
        handle_factory=factory,
    )
    await client.start()
    await client.create_rtsp(
        RtspMountpointSpec(
            url="rtsp://camera/live",
            description="camera",
            username="viewer",
            password="secret",
            reconnect_delay_seconds=7,
            session_timeout_seconds=8,
            media_timeout_seconds=9,
            connection_timeout_seconds=10,
            bind_interface="eth0",
            notify_changes=False,
            fail_check=True,
            quirk=False,
            permanent=True,
        )
    )

    request = dumped(handle.requests[0][1])
    assert request == {
        "request": "create",
        "admin_key": "admin-secret",
        "type": "rtsp",
        "description": "camera",
        "is_private": True,
        "permanent": True,
        "enabled": False,
        "media": [],
        "url": "rtsp://camera/live",
        "rtsp_user": "viewer",
        "rtsp_pwd": "secret",
        "rtsp_quirk": False,
        "rtsp_failcheck": True,
        "rtspiface": "eth0",
        "rtsp_reconnect_delay": 7,
        "rtsp_session_timeout": 8,
        "rtsp_timeout": 9,
        "rtsp_conn_timeout": 10,
        "rtsp_notify_changes": False,
    }


@pytest.mark.asyncio
async def test_edit_exposes_new_private_field() -> None:
    handle = FakeHandle([event_response({"streaming": "edited"})])

    async def factory(*args, **kwargs):
        return handle

    client = StreamingAdminClient(object(), handle_factory=factory)
    await client.start()
    await client.edit(
        12,
        secret="mount-secret",
        new_private=False,
        permanent=True,
        edited_event=True,
    )

    assert dumped(handle.requests[0][1]) == {
        "request": "edit",
        "id": 12,
        "secret": "mount-secret",
        "new_is_private": False,
        "permanent": True,
        "edited_event": True,
    }


@pytest.mark.asyncio
async def test_admin_maps_janus_level_and_plugin_level_errors() -> None:
    janus_error = SimpleNamespace(
        janus="error",
        error=SimpleNamespace(code=455, reason="No such mountpoint"),
    )
    plugin_error = event_response({"error_code": 456, "error": "Invalid element"})
    handle = FakeHandle([janus_error, plugin_error])

    async def factory(*args, **kwargs):
        return handle

    client = StreamingAdminClient(object(), handle_factory=factory)
    await client.start()

    with pytest.raises(JanusCommandError) as first:
        await client.list_mountpoints()
    assert first.value.code == 455

    with pytest.raises(JanusCommandError) as second:
        await client.list_mountpoints()
    assert second.value.code == 456


@pytest.mark.asyncio
async def test_viewer_normalizes_empty_media_resume_and_trickle() -> None:
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
    await viewer.prepare(media=())
    watch = dumped(handle.requests[0][1])
    assert watch["media"] == []

    await viewer.accept_answer(SessionDescription(type="answer", sdp="v=0\r\n"))
    await viewer.add_ice_candidate(
        IceCandidate(
            candidate="candidate:1 1 UDP 1 192.0.2.1 5000 typ host",
            sdpMid="video",
            sdpMLineIndex=1,
        )
    )
    await viewer.complete_ice()
    assert dumped(handle.trickles[0][0]) == {
        "sdpMid": "video",
        "sdpMLineIndex": 1,
        "candidate": "candidate:1 1 UDP 1 192.0.2.1 5000 typ host",
    }
    assert dumped(handle.trickles[1][0]) == {"completed": True}

    await viewer.pause()
    await viewer.resume()
    resume_operation, resume_request, resume_jsep = handle.requests[3]
    assert resume_operation == "resume"
    assert dumped(resume_request) == {"request": "start"}
    assert resume_jsep is None


@pytest.mark.asyncio
async def test_viewer_rejects_invalid_order_and_close_is_idempotent() -> None:
    handle = FakeHandle([])

    async def factory(*args, **kwargs):
        return handle

    viewer = StreamingViewer(object(), mountpoint_id=10, handle_factory=factory)
    with pytest.raises(InvalidViewerState):
        await viewer.accept_answer(SessionDescription(type="answer", sdp="v=0\r\n"))

    await viewer.close()
    await viewer.close()
    assert handle.closed is False


def test_public_configuration_validation() -> None:
    with pytest.raises(ValueError, match="max_concurrency"):
        StreamingAdminClient(object(), max_concurrency=0)
    with pytest.raises(ValueError, match="mountpoint_id"):
        StreamingViewer(object(), mountpoint_id=-1)
    with pytest.raises(ValueError, match="default_timeout"):
        _compat.JanusStreamingHandle(object(), default_timeout=0)
