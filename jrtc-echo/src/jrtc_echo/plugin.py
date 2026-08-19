"""Async EchoTest plugin handle."""

from __future__ import annotations

from jrtc.lib import Plugin
from jrtc.models.base import Jsep

from .errors import EchoTestProtocolError
from .models import (
    EchoTestReply,
    EchoTestRequest,
    EchoTestResponse,
    parse_echotest_response,
)


def _offer(value: Jsep) -> Jsep:
    if value.type != "offer":
        raise EchoTestProtocolError("EchoTest negotiation requires a JSEP offer")
    if not value.sdp.strip():
        raise EchoTestProtocolError("JSEP SDP must not be blank")
    return value


class EchoTestPlugin(Plugin):
    """Typed handle for ``janus.plugin.echotest``."""

    identifier = "echotest"
    name = "janus.plugin.echotest"

    async def request(
        self,
        body: EchoTestRequest,
        *,
        jsep: Jsep | None = None,
        timeout: float | None = None,
    ) -> EchoTestReply[EchoTestResponse]:
        """Send the plugin's unnamed request, optionally with an SDP offer."""

        response = await super().send(
            body,
            _offer(jsep) if jsep is not None else None,
            timeout=timeout,
            wait_for_event=True,
        )
        return parse_echotest_response(response)

    async def configure(
        self,
        *,
        audio: bool | None = None,
        audiocodec: str | None = None,
        video: bool | None = None,
        videocodec: str | None = None,
        videoprofile: str | None = None,
        bitrate: int | None = None,
        record: bool | None = None,
        filename: str | None = None,
        substream: int | None = None,
        temporal: int | None = None,
        svc: bool | None = None,
        spatial_layer: int | None = None,
        temporal_layer: int | None = None,
        timeout: float | None = None,
    ) -> EchoTestReply[EchoTestResponse]:
        """Change echoing, codecs, bitrate, recording, or selected layers."""

        body = EchoTestRequest(
            audio=audio,
            audiocodec=audiocodec,
            video=video,
            videocodec=videocodec,
            videoprofile=videoprofile,
            bitrate=bitrate,
            record=record,
            filename=filename,
            substream=substream,
            temporal=temporal,
            svc=svc,
            spatial_layer=spatial_layer,
            temporal_layer=temporal_layer,
        )
        return await self.request(body, timeout=timeout)

    async def negotiate(
        self,
        offer: Jsep,
        *,
        settings: EchoTestRequest | None = None,
        audio: bool | None = None,
        video: bool | None = None,
        bitrate: int | None = None,
        timeout: float | None = None,
    ) -> EchoTestReply[EchoTestResponse]:
        """Negotiate or renegotiate using a client-generated JSEP offer."""

        if settings is not None and any(value is not None for value in (audio, video, bitrate)):
            raise ValueError("pass settings or convenience fields, not both")
        body = settings or EchoTestRequest(audio=audio, video=video, bitrate=bitrate)
        reply = await self.request(body, jsep=_offer(offer), timeout=timeout)
        if reply.jsep is None or reply.jsep.type != "answer":
            raise EchoTestProtocolError("successful EchoTest negotiation must return a JSEP answer")
        return reply
