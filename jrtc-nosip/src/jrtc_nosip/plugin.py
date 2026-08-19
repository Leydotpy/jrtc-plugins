"""Async NoSIP plugin handle."""

from __future__ import annotations

from typing import Literal

from jrtc.lib import Plugin
from jrtc.models.base import Jsep
from jrtc.models.common import JanusId

from .errors import NoSipProtocolError
from .models import (
    ForwardStream,
    GenerateRequest,
    HangupRequest,
    KeyframeRequest,
    ListForwardersRequest,
    NoSipReply,
    NoSipResponse,
    ProcessRequest,
    RecordingRequest,
    RtpForwardRequest,
    SrtpPolicy,
    StopRtpForwardRequest,
    parse_nosip_response,
)


def _jsep(value: Jsep) -> Jsep:
    if value.type not in {"offer", "answer"}:
        raise NoSipProtocolError("generate requires a JSEP offer or answer")
    if not value.sdp.strip():
        raise NoSipProtocolError("JSEP SDP must not be blank")
    return value


class NoSipPlugin(Plugin):
    """Typed handle for ``janus.plugin.nosip``."""

    identifier = "nosip"
    name = "janus.plugin.nosip"

    async def _request(
        self,
        body: GenerateRequest
        | ProcessRequest
        | HangupRequest
        | RecordingRequest
        | KeyframeRequest
        | RtpForwardRequest
        | StopRtpForwardRequest
        | ListForwardersRequest,
        *,
        jsep: Jsep | None = None,
        timeout: float | None = None,
    ) -> NoSipReply[NoSipResponse]:
        response = await super().send(body, jsep, timeout=timeout, wait_for_event=True)
        return parse_nosip_response(response)

    async def generate(
        self,
        jsep: Jsep,
        *,
        info: str | None = None,
        srtp: SrtpPolicy | None = None,
        srtp_profile: str | None = None,
        timeout: float | None = None,
    ) -> NoSipReply[NoSipResponse]:
        """Convert an outer WebRTC JSEP offer/answer to bare SDP."""

        body = GenerateRequest(info=info, srtp=srtp, srtp_profile=srtp_profile)
        return await self._request(body, jsep=_jsep(jsep), timeout=timeout)

    async def process(
        self,
        type: Literal["offer", "answer"],
        sdp: str,
        *,
        info: str | None = None,
        srtp: SrtpPolicy | None = None,
        srtp_profile: str | None = None,
        timeout: float | None = None,
    ) -> NoSipReply[NoSipResponse]:
        """Convert bare SDP to the JSEP returned in the outer event."""

        body = ProcessRequest(
            type=type,
            sdp=sdp,
            info=info,
            srtp=srtp,
            srtp_profile=srtp_profile,
        )
        reply = await self._request(body, timeout=timeout)
        if reply.jsep is None or reply.jsep.type != type:
            raise NoSipProtocolError(f"successful process({type!r}) must return a JSEP {type}")
        return reply

    async def hangup(self, *, timeout: float | None = None) -> NoSipReply[NoSipResponse]:
        """Terminate the active bridged media session."""

        return await self._request(HangupRequest(), timeout=timeout)

    async def recording(
        self,
        action: Literal["start", "stop"],
        *,
        audio: bool | None = None,
        video: bool | None = None,
        peer_audio: bool | None = None,
        peer_video: bool | None = None,
        filename: str | None = None,
        timeout: float | None = None,
    ) -> NoSipReply[NoSipResponse]:
        """Start or stop selected local/peer audio/video recorders."""

        body = RecordingRequest(
            action=action,
            audio=audio,
            video=video,
            peer_audio=peer_audio,
            peer_video=peer_video,
            filename=filename,
        )
        return await self._request(body, timeout=timeout)

    async def keyframe(
        self,
        *,
        user: bool | None = None,
        peer: bool | None = None,
        timeout: float | None = None,
    ) -> NoSipReply[NoSipResponse]:
        """Request a keyframe from the WebRTC user, RTP peer, or both."""

        return await self._request(KeyframeRequest(user=user, peer=peer), timeout=timeout)

    async def rtp_forward(
        self,
        streams: list[ForwardStream],
        *,
        timeout: float | None = None,
    ) -> NoSipReply[NoSipResponse]:
        """Create one or more RTP forwarders."""

        return await self._request(RtpForwardRequest(streams=streams), timeout=timeout)

    async def stop_rtp_forward(
        self, stream_id: JanusId, *, timeout: float | None = None
    ) -> NoSipReply[NoSipResponse]:
        """Stop one forwarder by its Janus-assigned stream id."""

        return await self._request(StopRtpForwardRequest(stream_id=stream_id), timeout=timeout)

    async def list_forwarders(self, *, timeout: float | None = None) -> NoSipReply[NoSipResponse]:
        """List active RTP forwarders for the current call."""

        return await self._request(ListForwardersRequest(), timeout=timeout)


NoSIPPlugin = NoSipPlugin
