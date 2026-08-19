"""Async handle for the Janus AudioBridge plugin."""

from __future__ import annotations

from jrtc.lib import Plugin
from jrtc.models.base import Jsep

from .errors import AudioBridgeProtocolError
from .models import (
    AudioBridgeAllowedRequest,
    AudioBridgeChangeRoomRequest,
    AudioBridgeConfigureRequest,
    AudioBridgeCreateRequest,
    AudioBridgeDestroyRequest,
    AudioBridgeEditRequest,
    AudioBridgeEnableMjrsRequest,
    AudioBridgeEnableRecordingRequest,
    AudioBridgeExistsRequest,
    AudioBridgeIsPlayingRequest,
    AudioBridgeJoinRequest,
    AudioBridgeKickAllRequest,
    AudioBridgeKickRequest,
    AudioBridgeLeaveRequest,
    AudioBridgeListAnnouncementsRequest,
    AudioBridgeListForwardersRequest,
    AudioBridgeListParticipantsRequest,
    AudioBridgeListRequest,
    AudioBridgeMuteRequest,
    AudioBridgeMuteRoomRequest,
    AudioBridgePlayFileRequest,
    AudioBridgeReply,
    AudioBridgeRequest,
    AudioBridgeResetDecoderRequest,
    AudioBridgeResponse,
    AudioBridgeResumeRequest,
    AudioBridgeRtpForwardRequest,
    AudioBridgeRtpTransport,
    AudioBridgeStopAllFilesRequest,
    AudioBridgeStopFileRequest,
    AudioBridgeStopRtpForwardRequest,
    AudioBridgeSuspendRequest,
    AudioBridgeUnmuteRequest,
    AudioBridgeUnmuteRoomRequest,
    RoomId,
    parse_audiobridge_response,
)


def _validate_jsep(jsep: Jsep) -> Jsep:
    if jsep.type not in {"offer", "answer"}:
        raise AudioBridgeProtocolError("AudioBridge requires a JSEP offer or answer")
    if not jsep.sdp.strip():
        raise AudioBridgeProtocolError("JSEP SDP must not be blank")
    return jsep


class AudioBridgePlugin(Plugin):
    """Typed handle for ``janus.plugin.audiobridge``.

    The handle does not own its Janus session. Use it as an async context
    manager, or call ``attach``/``detach`` explicitly.
    """

    identifier = "audiobridge"
    name = "janus.plugin.audiobridge"

    async def request(
        self,
        body: AudioBridgeRequest,
        *,
        jsep: Jsep | None = None,
        timeout: float | None = None,
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        """Send any validated AudioBridge request body.

        JSEP is legal only with ``join`` and ``configure``. A client offer and
        a plugin-generated offer are mutually exclusive, and plain RTP never
        carries JSEP.
        """

        if jsep is not None:
            _validate_jsep(jsep)
            if not isinstance(
                body, (AudioBridgeJoinRequest, AudioBridgeConfigureRequest)
            ):
                raise AudioBridgeProtocolError(
                    "JSEP is only valid with AudioBridge join or configure"
                )
            if body.generate_offer:
                raise AudioBridgeProtocolError(
                    "generate_offer cannot be combined with a client JSEP"
                )
            if body.rtp is not None:
                raise AudioBridgeProtocolError("plain-RTP requests cannot carry JSEP")
            if jsep.type == "answer" and not isinstance(
                body, AudioBridgeConfigureRequest
            ):
                raise AudioBridgeProtocolError(
                    "an answer to a plugin offer must be sent with configure"
                )

        response = await super().send(
            body,
            jsep,
            timeout=timeout,
            wait_for_event=True,
        )
        return parse_audiobridge_response(response)

    async def create(
        self, body: AudioBridgeCreateRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def edit(
        self, body: AudioBridgeEditRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def destroy(
        self, body: AudioBridgeDestroyRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def enable_recording(
        self, body: AudioBridgeEnableRecordingRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        """Toggle mixed-room WAV recording."""

        return await self.request(body, timeout=timeout)

    async def enable_mjrs(
        self, body: AudioBridgeEnableMjrsRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        """Toggle per-participant MJR recording in bulk."""

        return await self.request(body, timeout=timeout)

    async def exists(
        self, room: RoomId, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(AudioBridgeExistsRequest(room=room), timeout=timeout)

    async def allowed(
        self, body: AudioBridgeAllowedRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def kick(
        self, body: AudioBridgeKickRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def kick_all(
        self, body: AudioBridgeKickAllRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def suspend(
        self, body: AudioBridgeSuspendRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def resume(
        self, body: AudioBridgeResumeRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def list_rooms(
        self, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(AudioBridgeListRequest(), timeout=timeout)

    async def list_participants(
        self, room: RoomId, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(
            AudioBridgeListParticipantsRequest(room=room), timeout=timeout
        )

    async def reset_decoder(
        self, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(AudioBridgeResetDecoderRequest(), timeout=timeout)

    async def mute(
        self, body: AudioBridgeMuteRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def unmute(
        self, body: AudioBridgeUnmuteRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def mute_room(
        self, body: AudioBridgeMuteRoomRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def unmute_room(
        self, body: AudioBridgeUnmuteRoomRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def rtp_forward(
        self, body: AudioBridgeRtpForwardRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def stop_rtp_forward(
        self, body: AudioBridgeStopRtpForwardRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def list_forwarders(
        self, room: RoomId, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(
            AudioBridgeListForwardersRequest(room=room), timeout=timeout
        )

    async def play_file(
        self, body: AudioBridgePlayFileRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def is_playing(
        self, body: AudioBridgeIsPlayingRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def list_announcements(
        self, body: AudioBridgeListAnnouncementsRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def stop_file(
        self, body: AudioBridgeStopFileRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def stop_all_files(
        self, body: AudioBridgeStopAllFilesRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, timeout=timeout)

    async def join(
        self,
        body: AudioBridgeJoinRequest,
        *,
        jsep: Jsep | None = None,
        timeout: float | None = None,
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(body, jsep=jsep, timeout=timeout)

    async def configure(
        self,
        body: AudioBridgeConfigureRequest | None = None,
        *,
        jsep: Jsep | None = None,
        timeout: float | None = None,
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(
            body or AudioBridgeConfigureRequest(), jsep=jsep, timeout=timeout
        )

    async def leave(
        self, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        return await self.request(AudioBridgeLeaveRequest(), timeout=timeout)

    async def change_room(
        self, body: AudioBridgeChangeRoomRequest, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        """Move rooms while reusing the existing PeerConnection (no JSEP)."""

        return await self.request(body, timeout=timeout)

    async def negotiate(
        self,
        offer: Jsep,
        *,
        settings: AudioBridgeConfigureRequest | None = None,
        timeout: float | None = None,
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        """Complete the normal client-offer / AudioBridge-answer flow."""

        if offer.type != "offer":
            raise AudioBridgeProtocolError("negotiate requires a JSEP offer")
        return await self.configure(settings, jsep=offer, timeout=timeout)

    async def request_offer(
        self,
        room: RoomId | None = None,
        *,
        join: AudioBridgeJoinRequest | None = None,
        plain_rtp: bool = False,
        timeout: float | None = None,
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        """Join and ask AudioBridge to originate the JSEP or RTP offer.

        ``plain_rtp=True`` deliberately sends an empty ``rtp`` object so Janus
        returns its listening endpoint before the remote endpoint is known.
        Pass a typed ``join`` model for additional participant options.
        """

        if (room is None) == (join is None):
            raise ValueError("pass exactly one of room or join")
        body = join or AudioBridgeJoinRequest(room=room)
        if body.generate_offer is not None or body.rtp is not None:
            raise ValueError("generate_offer and rtp are controlled by request_offer")
        body = body.model_copy(
            update={
                "generate_offer": True,
                "rtp": AudioBridgeRtpTransport() if plain_rtp else None,
            }
        )
        return await self.join(body, timeout=timeout)

    async def answer_offer(
        self,
        answer: Jsep,
        *,
        settings: AudioBridgeConfigureRequest | None = None,
        timeout: float | None = None,
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        """Answer an AudioBridge-originated offer with ``configure``."""

        if answer.type != "answer":
            raise AudioBridgeProtocolError("answer_offer requires a JSEP answer")
        return await self.configure(settings, jsep=answer, timeout=timeout)

    async def request_renegotiation_offer(
        self, *, timeout: float | None = None
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        """Preserve plugin-offerer roles during a later renegotiation."""

        return await self.configure(
            AudioBridgeConfigureRequest(generate_offer=True), timeout=timeout
        )

    async def complete_plain_rtp(
        self,
        endpoint: AudioBridgeRtpTransport,
        *,
        timeout: float | None = None,
    ) -> AudioBridgeReply[AudioBridgeResponse]:
        """Provide the remote endpoint after a reversed plain-RTP offer."""

        if endpoint.ip is None or endpoint.port is None:
            raise ValueError("a completed plain-RTP endpoint requires ip and port")
        return await self.configure(
            AudioBridgeConfigureRequest(rtp=endpoint), timeout=timeout
        )
