"""Async Record&Play handle with an explicit JSEP state machine."""

from __future__ import annotations

from typing import Type

from jrtc.lib import Plugin
from jrtc.models.base import Jsep
from jrtc.models.common import JanusId

from .errors import RecordPlayProtocolError
from .models import (
    ConfigureRequest,
    ListRequest,
    PauseRequest,
    PlayRequest,
    RecordPlayReply,
    RecordPlayResponse,
    RecordRequest,
    ResumeRequest,
    StartRequest,
    StopRequest,
    UpdateRequest,
    parse_recordplay_response,
)


def _jsep(value: Jsep, expected: str, operation: str) -> Jsep:
    if value.type != expected:
        raise RecordPlayProtocolError(f"{operation} requires a JSEP {expected}")
    if not value.sdp.strip():
        raise RecordPlayProtocolError("JSEP SDP must not be blank")
    return value


class RecordPlayPlugin(Plugin):
    """Typed handle for ``janus.plugin.recordplay``."""

    identifier = "recordplay"
    name = "janus.plugin.recordplay"

    async def _request(
        self,
        body: ListRequest
        | UpdateRequest
        | ConfigureRequest
        | RecordRequest
        | PlayRequest
        | StartRequest
        | PauseRequest
        | ResumeRequest
        | StopRequest,
        *,
        jsep: Jsep | None = None,
        synchronous: bool = False,
        timeout: float | None = None,
    ) -> RecordPlayReply[Type[RecordPlayResponse]]:
        response = await super().send(
            body,
            jsep,
            timeout=timeout,
            wait_for_event=not synchronous,
        )
        return parse_recordplay_response(response)

    async def list_recordings(
        self,
        *,
        admin_key: str | None = None,
        timeout: float | None = None,
    ) -> RecordPlayReply[Type[RecordPlayResponse]]:
        """Synchronously list public recordings (and private ones with admin key)."""

        return await self._request(
            ListRequest(admin_key=admin_key), synchronous=True, timeout=timeout
        )

    async def update(
        self,
        *,
        admin_key: str | None = None,
        timeout: float | None = None,
    ) -> RecordPlayReply[Type[RecordPlayResponse]]:
        """Synchronously rescan the recordings directory."""

        return await self._request(
            UpdateRequest(admin_key=admin_key), synchronous=True, timeout=timeout
        )

    async def configure(
        self,
        *,
        video_bitrate_max: int | None = None,
        video_keyframe_interval: int | None = None,
        timeout: float | None = None,
    ) -> RecordPlayReply[Type[RecordPlayResponse]]:
        """Synchronously adjust playback bitrate/keyframe rewrite settings."""

        body = ConfigureRequest(
            video_bitrate_max=video_bitrate_max,
            video_keyframe_interval=video_keyframe_interval,
        )
        return await self._request(body, synchronous=True, timeout=timeout)

    async def record(
        self,
        name: str,
        offer: Jsep,
        *,
        recording_id: JanusId | None = None,
        is_private: bool | None = None,
        filename: str | None = None,
        audiocodec: str | None = None,
        videocodec: str | None = None,
        videoprofile: str | None = None,
        opusred: bool | None = None,
        textdata: bool | None = None,
        update: bool | None = None,
        timeout: float | None = None,
    ) -> RecordPlayReply[Type[RecordPlayResponse]]:
        """Start recording from a client offer; Janus answers in the reply."""

        body = RecordRequest(
            id=recording_id,
            name=name,
            is_private=is_private,
            filename=filename,
            audiocodec=audiocodec,
            videocodec=videocodec,
            videoprofile=videoprofile,
            opusred=opusred,
            textdata=textdata,
            update=update,
        )
        reply = await self._request(
            body,
            jsep=_jsep(offer, "offer", "record"),
            timeout=timeout,
        )
        if reply.jsep is None or reply.jsep.type != "answer":
            raise RecordPlayProtocolError("successful record request must return a JSEP answer")
        return reply

    async def play(
        self,
        recording_id: JanusId,
        *,
        restart: bool | None = None,
        timeout: float | None = None,
    ) -> RecordPlayReply[Type[RecordPlayResponse]]:
        """Prepare playback without JSEP; Janus returns an outer offer."""

        reply = await self._request(PlayRequest(id=recording_id, restart=restart), timeout=timeout)
        if reply.jsep is None or reply.jsep.type != "offer":
            raise RecordPlayProtocolError(
                "successful play request must return a Janus-generated JSEP offer"
            )
        return reply

    async def start(
        self, answer: Jsep, *, timeout: float | None = None
    ) -> RecordPlayReply[Type[RecordPlayResponse]]:
        """Start prepared playback using the client's JSEP answer."""

        return await self._request(
            StartRequest(),
            jsep=_jsep(answer, "answer", "start"),
            timeout=timeout,
        )

    async def pause(self, *, timeout: float | None = None) -> RecordPlayReply[Type[RecordPlayResponse]]:
        """Pause the active recording or playback session."""

        return await self._request(PauseRequest(), timeout=timeout)

    async def resume(self, *, timeout: float | None = None) -> RecordPlayReply[Type[RecordPlayResponse]]:
        """Resume a paused recording or playback session."""

        return await self._request(ResumeRequest(), timeout=timeout)

    async def stop(self, *, timeout: float | None = None) -> RecordPlayReply[Type[RecordPlayResponse]]:
        """Stop the active Record&Play operation."""

        return await self._request(StopRequest(), timeout=timeout)
