"""Async client covering the complete Janus SIP plugin API."""

from __future__ import annotations

from typing import Literal

from jrtc.lib import Plugin
from jrtc.models.base import Jsep
from jrtc.models.common import JanusId

from .errors import SipProtocolError
from .models import (
    AcceptRequest,
    CallRequest,
    ContactParams,
    DeclineRequest,
    DtmfInfoRequest,
    ForwardStream,
    HangupRequest,
    Headers,
    HoldRequest,
    InfoRequest,
    KeyframeRequest,
    ListForwardersRequest,
    MessageRequest,
    ProgressRequest,
    RecordingRequest,
    RegisterRequest,
    RtpForwardRequest,
    SipReply,
    SipRequest,
    SipResponse,
    SrtpPolicy,
    StopRtpForwardRequest,
    SubscribeRequest,
    TransferRequest,
    UnholdRequest,
    UnregisterRequest,
    UnsubscribeRequest,
    UpdateRequest,
    parse_sip_response,
)


def _jsep(value: Jsep, allowed: set[str], operation: str) -> Jsep:
    if value.type not in allowed:
        expected = " or ".join(sorted(allowed))
        raise SipProtocolError(f"{operation} requires JSEP type {expected}")
    if not value.sdp.strip():
        raise SipProtocolError("JSEP SDP must not be blank")
    return value


def _update_jsep(value: Jsep) -> Jsep:
    """Mark offer/answer JSEP as a Janus renegotiation description."""

    return _jsep(value, {"offer", "answer"}, "update").model_copy(update={"update": True})


class SipPlugin(Plugin):
    """Typed handle for ``janus.plugin.sip``."""

    identifier = "sip"
    name = "janus.plugin.sip"

    async def send_request(
        self,
        body: SipRequest,
        *,
        jsep: Jsep | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Send one validated asynchronous SIP operation."""

        response = await super().send(
            body,
            jsep,
            timeout=timeout,
            wait_for_event=True,
        )
        return parse_sip_response(response)

    async def register(
        self,
        username: str,
        *,
        registration_type: Literal["guest", "helper"] | None = None,
        send_register: bool | None = None,
        force_udp: bool | None = None,
        force_tcp: bool | None = None,
        sips: bool | None = None,
        rfc2543_cancel: bool | None = None,
        automatic_ringing: bool | None = None,
        secret: str | None = None,
        ha1_secret: str | None = None,
        authuser: str | None = None,
        display_name: str | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
        outbound_proxy: str | None = None,
        headers: Headers | None = None,
        contact_params: ContactParams | None = None,
        incoming_header_prefixes: list[str] | None = None,
        refresh: bool | None = None,
        master_id: JanusId | None = None,
        register_ttl: int | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Register a normal, guest, or helper SIP identity."""

        body = RegisterRequest(
            type=registration_type,
            send_register=send_register,
            force_udp=force_udp,
            force_tcp=force_tcp,
            sips=sips,
            rfc2543_cancel=rfc2543_cancel,
            automatic_ringing=automatic_ringing,
            username=username,
            secret=secret,
            ha1_secret=ha1_secret,
            authuser=authuser,
            display_name=display_name,
            user_agent=user_agent,
            proxy=proxy,
            outbound_proxy=outbound_proxy,
            headers=headers,
            contact_params=contact_params,
            incoming_header_prefixes=incoming_header_prefixes,
            refresh=refresh,
            master_id=master_id,
            register_ttl=register_ttl,
        )
        return await self.send_request(body, timeout=timeout)

    async def register_account(
        self,
        username: str,
        *,
        secret: str | None = None,
        ha1_secret: str | None = None,
        authuser: str | None = None,
        send_register: bool | None = None,
        force_udp: bool | None = None,
        force_tcp: bool | None = None,
        sips: bool | None = None,
        rfc2543_cancel: bool | None = None,
        automatic_ringing: bool | None = None,
        proxy: str | None = None,
        outbound_proxy: str | None = None,
        display_name: str | None = None,
        user_agent: str | None = None,
        headers: Headers | None = None,
        contact_params: ContactParams | None = None,
        incoming_header_prefixes: list[str] | None = None,
        refresh: bool | None = None,
        register_ttl: int | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Convenience wrapper for a credentialed normal registration."""

        return await self.register(
            username,
            secret=secret,
            ha1_secret=ha1_secret,
            authuser=authuser,
            send_register=send_register,
            force_udp=force_udp,
            force_tcp=force_tcp,
            sips=sips,
            rfc2543_cancel=rfc2543_cancel,
            automatic_ringing=automatic_ringing,
            proxy=proxy,
            outbound_proxy=outbound_proxy,
            display_name=display_name,
            user_agent=user_agent,
            headers=headers,
            contact_params=contact_params,
            incoming_header_prefixes=incoming_header_prefixes,
            refresh=refresh,
            register_ttl=register_ttl,
            timeout=timeout,
        )

    async def register_guest(
        self,
        username: str,
        *,
        display_name: str | None = None,
        headers: Headers | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Use a SIP identity without sending REGISTER or storing credentials."""

        return await self.register(
            username,
            registration_type="guest",
            display_name=display_name,
            headers=headers,
            timeout=timeout,
        )

    async def register_helper(
        self,
        username: str,
        master_id: JanusId,
        *,
        incoming_header_prefixes: list[str] | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Associate this handle with an already registered master account."""

        return await self.register(
            username,
            registration_type="helper",
            master_id=master_id,
            incoming_header_prefixes=incoming_header_prefixes,
            timeout=timeout,
        )

    async def unregister(self, *, timeout: float | None = None) -> SipReply[SipResponse]:
        """Unregister the current account and await its initial status event."""

        return await self.send_request(UnregisterRequest(), timeout=timeout)

    async def call(
        self,
        uri: str,
        offer: Jsep,
        *,
        call_id: str | None = None,
        refer_id: JanusId | None = None,
        headers: Headers | None = None,
        srtp: SrtpPolicy | None = None,
        srtp_profile: str | None = None,
        secret: str | None = None,
        ha1_secret: str | None = None,
        authuser: str | None = None,
        autoaccept_reinvites: bool | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Send an INVITE with the mandatory WebRTC offer."""

        body = CallRequest(
            uri=uri,
            call_id=call_id,
            refer_id=refer_id,
            headers=headers,
            srtp=srtp,
            srtp_profile=srtp_profile,
            secret=secret,
            ha1_secret=ha1_secret,
            authuser=authuser,
            autoaccept_reinvites=autoaccept_reinvites,
        )
        return await self.send_request(
            body,
            jsep=_jsep(offer, {"offer"}, "call"),
            timeout=timeout,
        )

    async def progress(
        self,
        jsep: Jsep,
        *,
        srtp: SrtpPolicy | None = None,
        srtp_profile: str | None = None,
        headers: Headers | None = None,
        autoaccept_reinvites: bool | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Send 183 with an answer, or an offer for an offerless INVITE."""

        body = ProgressRequest(
            srtp=srtp,
            srtp_profile=srtp_profile,
            headers=headers,
            autoaccept_reinvites=autoaccept_reinvites,
        )
        return await self.send_request(
            body,
            jsep=_jsep(jsep, {"offer", "answer"}, "progress"),
            timeout=timeout,
        )

    async def accept(
        self,
        jsep: Jsep,
        *,
        srtp: SrtpPolicy | None = None,
        srtp_profile: str | None = None,
        headers: Headers | None = None,
        autoaccept_reinvites: bool | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Accept an INVITE with answer JSEP, or offer JSEP if it was offerless."""

        body = AcceptRequest(
            srtp=srtp,
            srtp_profile=srtp_profile,
            headers=headers,
            autoaccept_reinvites=autoaccept_reinvites,
        )
        return await self.send_request(
            body,
            jsep=_jsep(jsep, {"offer", "answer"}, "accept"),
            timeout=timeout,
        )

    async def update(self, jsep: Jsep, *, timeout: float | None = None) -> SipReply[SipResponse]:
        """Send an offer for a local update or answer an incoming re-INVITE."""

        return await self.send_request(
            UpdateRequest(),
            jsep=_update_jsep(jsep),
            timeout=timeout,
        )

    async def decline(
        self,
        *,
        code: int | None = None,
        refer_id: JanusId | None = None,
        headers: Headers | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Decline an INVITE, or decline an incoming REFER by ``refer_id``."""

        return await self.send_request(
            DeclineRequest(code=code, refer_id=refer_id, headers=headers),
            timeout=timeout,
        )

    async def hold(
        self,
        direction: Literal["sendonly", "recvonly", "inactive"] | None = None,
        *,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Put the active call on hold with an optional SDP direction."""

        return await self.send_request(HoldRequest(direction=direction), timeout=timeout)

    async def unhold(self, *, timeout: float | None = None) -> SipReply[SipResponse]:
        """Resume media on the active held call."""

        return await self.send_request(UnholdRequest(), timeout=timeout)

    async def hangup(
        self,
        *,
        headers: Headers | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Terminate the active call and optionally add SIP headers."""

        return await self.send_request(HangupRequest(headers=headers), timeout=timeout)

    async def message(
        self,
        content: str,
        *,
        content_type: str | None = None,
        uri: str | None = None,
        call_id: str | None = None,
        headers: Headers | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Send an in-dialog or out-of-dialog SIP MESSAGE."""

        body = MessageRequest(
            content=content,
            content_type=content_type,
            uri=uri,
            call_id=call_id,
            headers=headers,
        )
        return await self.send_request(body, timeout=timeout)

    async def info(
        self,
        content_type: str,
        content: str,
        *,
        headers: Headers | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Send an in-dialog SIP INFO request."""

        return await self.send_request(
            InfoRequest(type=content_type, content=content, headers=headers),
            timeout=timeout,
        )

    async def dtmf_info(
        self,
        digit: str,
        *,
        duration: int | None = None,
        headers: Headers | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Send one DTMF signal using a SIP INFO request."""

        return await self.send_request(
            DtmfInfoRequest(digit=digit, duration=duration, headers=headers),
            timeout=timeout,
        )

    async def subscribe(
        self,
        event: str,
        *,
        to: str | None = None,
        accept: str | None = None,
        call_id: str | None = None,
        subscribe_ttl: int | None = None,
        content: str | None = None,
        content_type: str | None = None,
        headers: Headers | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Create or refresh a SIP event subscription."""

        body = SubscribeRequest(
            event=event,
            to=to,
            accept=accept,
            call_id=call_id,
            subscribe_ttl=subscribe_ttl,
            content=content,
            content_type=content_type,
            headers=headers,
        )
        return await self.send_request(body, timeout=timeout)

    async def unsubscribe(
        self,
        event: str,
        *,
        to: str | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """End the subscription identified by its event name and target."""

        return await self.send_request(UnsubscribeRequest(event=event, to=to), timeout=timeout)

    async def transfer(
        self,
        uri: str,
        *,
        replace: str | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Start a blind transfer, or an attended transfer with ``replace``."""

        return await self.send_request(TransferRequest(uri=uri, replace=replace), timeout=timeout)

    async def recording(
        self,
        action: Literal["start", "stop", "pause", "resume"],
        *,
        audio: bool | None = None,
        video: bool | None = None,
        peer_audio: bool | None = None,
        peer_video: bool | None = None,
        send_peer_pli: bool | None = None,
        filename: str | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Start, pause, resume, or stop selected call-side recordings."""

        body = RecordingRequest(
            action=action,
            audio=audio,
            video=video,
            peer_audio=peer_audio,
            peer_video=peer_video,
            send_peer_pli=send_peer_pli,
            filename=filename,
        )
        return await self.send_request(body, timeout=timeout)

    async def keyframe(
        self,
        *,
        user: bool | None = None,
        peer: bool | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Request a video keyframe from the WebRTC user, SIP peer, or both."""

        return await self.send_request(KeyframeRequest(user=user, peer=peer), timeout=timeout)

    async def rtp_forward(
        self,
        streams: list[ForwardStream],
        *,
        unique_id: str | None = None,
        admin_key: str | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Create RTP forwarders for selected local or peer media streams."""

        return await self.send_request(
            RtpForwardRequest(
                streams=streams,
                unique_id=unique_id,
                admin_key=admin_key,
            ),
            timeout=timeout,
        )

    async def stop_rtp_forward(
        self,
        streams: list[int] | None = None,
        *,
        stream_id: JanusId | None = None,
        unique_id: str | None = None,
        admin_key: str | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """Stop multiple forwarders, or use legacy ``stream_id`` syntax."""

        return await self.send_request(
            StopRtpForwardRequest(
                streams=streams,
                stream_id=stream_id,
                unique_id=unique_id,
                admin_key=admin_key,
            ),
            timeout=timeout,
        )

    async def list_forwarders(
        self,
        *,
        unique_id: str | None = None,
        admin_key: str | None = None,
        timeout: float | None = None,
    ) -> SipReply[SipResponse]:
        """List RTP forwarders for this call or an addressed helper session."""

        return await self.send_request(
            ListForwardersRequest(unique_id=unique_id, admin_key=admin_key),
            timeout=timeout,
        )


SIPPlugin = SipPlugin
