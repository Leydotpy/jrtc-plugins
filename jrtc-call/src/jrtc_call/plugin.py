"""Async client for all Janus VideoCall operations."""

from __future__ import annotations

from jrtc.lib import Plugin
from jrtc.models.base import Jsep

from .errors import VideoCallProtocolError
from .models import (
    AcceptRequest,
    CallRequest,
    HangupRequest,
    ListRequest,
    RegisterRequest,
    SetRequest,
    VideoCallReply,
    VideoCallResponse,
    parse_videocall_response,
)


def _jsep(value: Jsep, allowed: set[str], operation: str) -> Jsep:
    if value.type not in allowed:
        expected = " or ".join(sorted(allowed))
        raise VideoCallProtocolError(f"{operation} requires JSEP type {expected}")
    if not value.sdp.strip():
        raise VideoCallProtocolError("JSEP SDP must not be blank")
    return value


class VideoCallPlugin(Plugin):
    """Typed handle for ``janus.plugin.videocall``."""

    identifier = "videocall"
    name = "janus.plugin.videocall"

    async def _request(
        self,
        body: (
            ListRequest | RegisterRequest | CallRequest | AcceptRequest | SetRequest | HangupRequest
        ),
        *,
        jsep: Jsep | None = None,
        timeout: float | None = None,
    ) -> VideoCallReply[VideoCallResponse]:
        response = await super().send(body, jsep, timeout=timeout, wait_for_event=True)
        return parse_videocall_response(response)

    async def list_peers(
        self, *, timeout: float | None = None
    ) -> VideoCallReply[VideoCallResponse]:
        """List usernames currently registered with this plugin instance."""

        return await self._request(ListRequest(), timeout=timeout)

    async def register(
        self, username: str, *, timeout: float | None = None
    ) -> VideoCallReply[VideoCallResponse]:
        """Register the handle under ``username``."""

        return await self._request(RegisterRequest(username=username), timeout=timeout)

    async def call(
        self, username: str, offer: Jsep, *, timeout: float | None = None
    ) -> VideoCallReply[VideoCallResponse]:
        """Call a peer using a client-generated JSEP offer."""

        return await self._request(
            CallRequest(username=username),
            jsep=_jsep(offer, {"offer"}, "call"),
            timeout=timeout,
        )

    async def accept(
        self, answer: Jsep, *, timeout: float | None = None
    ) -> VideoCallReply[VideoCallResponse]:
        """Accept an incoming call using the client's JSEP answer."""

        return await self._request(
            AcceptRequest(),
            jsep=_jsep(answer, {"answer"}, "accept"),
            timeout=timeout,
        )

    async def set(
        self,
        *,
        audio: bool | None = None,
        video: bool | None = None,
        bitrate: int | None = None,
        record: bool | None = None,
        filename: str | None = None,
        substream: int | None = None,
        temporal: int | None = None,
        fallback: int | None = None,
        jsep: Jsep | None = None,
        timeout: float | None = None,
    ) -> VideoCallReply[VideoCallResponse]:
        """Apply call settings and optionally renegotiate with offer/answer JSEP."""

        body = SetRequest(
            audio=audio,
            video=video,
            bitrate=bitrate,
            record=record,
            filename=filename,
            substream=substream,
            temporal=temporal,
            fallback=fallback,
        )
        if jsep is None and all(
            value is None
            for value in (
                audio,
                video,
                bitrate,
                record,
                filename,
                substream,
                temporal,
                fallback,
            )
        ):
            raise VideoCallProtocolError(
                "an empty set request is only valid when accompanied by JSEP"
            )
        negotiation = _jsep(jsep, {"offer", "answer"}, "set") if jsep is not None else None
        return await self._request(body, jsep=negotiation, timeout=timeout)

    async def hangup(self, *, timeout: float | None = None) -> VideoCallReply[VideoCallResponse]:
        """Cancel, decline, or terminate the current VideoCall call."""

        return await self._request(HangupRequest(), timeout=timeout)
