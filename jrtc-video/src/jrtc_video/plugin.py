"""Async typed handle for the Janus VideoRoom plugin."""

from __future__ import annotations

from typing import Literal, TypeAlias

from jrtc.lib import Plugin
from jrtc.models.base import Jsep

from .errors import VideoRoomProtocolError
from .models import (
    AddRemotePublisherRequest,
    JanusId,
    ListRemotesRequest,
    PublisherConfigureRequest,
    PublisherJoinAndConfigureRequest,
    PublisherJoinRequest,
    PublisherPublishRequest,
    PublisherUnpublishRequest,
    PublishRemotelyRequest,
    RemoveRemotePublisherRequest,
    SubscriberConfigureRequest,
    SubscriberJoinRequest,
    SubscriberPauseRequest,
    SubscriberStartRequest,
    SubscriberSubscribeRequest,
    SubscriberSwitchRequest,
    SubscriberUnsubscribeRequest,
    SubscriberUpdateRequest,
    UnpublishRemotelyRequest,
    UpdateRemotePublisherRequest,
    VideoRoomAllowedRequest,
    VideoRoomCreateRequest,
    VideoRoomDestroyRequest,
    VideoRoomEditRequest,
    VideoRoomEnableRecordingRequest,
    VideoRoomExistsRequest,
    VideoRoomKickRequest,
    VideoRoomLeaveRequest,
    VideoRoomListForwardersRequest,
    VideoRoomListParticipantsRequest,
    VideoRoomListRequest,
    VideoRoomModerateRequest,
    VideoRoomReply,
    VideoRoomRequest,
    VideoRoomResponse,
    VideoRoomRtpForwardRequest,
    VideoRoomStopRtpForwardRequest,
    parse_videoroom_response,
)


JsepRole: TypeAlias = Literal["offer", "answer"]


def _jsep(value: Jsep, expected: JsepRole) -> Jsep:
    if value.type != expected:
        raise VideoRoomProtocolError(
            f"expected a JSEP {expected}, received {value.type!r}"
        )
    if not value.sdp.strip():
        raise VideoRoomProtocolError("JSEP SDP must not be blank")
    return value


def _wire_body(body: VideoRoomRequest) -> dict[str, object]:
    """Serialize explicit fields while retaining command/role discriminators."""

    payload = body.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
        exclude_unset=True,
    )
    payload["request"] = body.request
    ptype = getattr(body, "ptype", None)
    if ptype is not None:
        payload["ptype"] = ptype
    return payload


class VideoRoomPlugin(Plugin):
    """Typed handle for ``janus.plugin.videoroom``."""

    identifier = "videoroom"
    name = "janus.plugin.videoroom"

    async def request(
        self,
        body: VideoRoomRequest,
        *,
        jsep: Jsep | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        """Send one validated request and parse the plugin response/event."""

        if jsep is not None:
            if isinstance(
                body,
                (
                    PublisherPublishRequest,
                    PublisherConfigureRequest,
                    PublisherJoinAndConfigureRequest,
                ),
            ):
                _jsep(jsep, "offer")
            elif isinstance(body, SubscriberStartRequest):
                _jsep(jsep, "answer")
            else:
                raise VideoRoomProtocolError(
                    "JSEP is only valid with publisher publish/configure/"
                    "joinandconfigure or subscriber start"
                )

        response = await super().send(
            _wire_body(body),
            jsep,
            timeout=timeout,
            wait_for_event=True,
        )
        return parse_videoroom_response(response)

    async def create(
        self, body: VideoRoomCreateRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def edit(
        self, body: VideoRoomEditRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def destroy(
        self, body: VideoRoomDestroyRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def exists(
        self, room: JanusId, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(VideoRoomExistsRequest(room=room), timeout=timeout)

    async def allowed(
        self, body: VideoRoomAllowedRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def kick(
        self, body: VideoRoomKickRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def moderate(
        self, body: VideoRoomModerateRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def enable_recording(
        self, body: VideoRoomEnableRecordingRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def list_rooms(
        self,
        *,
        admin_key: str | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(
            VideoRoomListRequest(admin_key=admin_key), timeout=timeout
        )

    async def list_participants(
        self, room: JanusId, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(
            VideoRoomListParticipantsRequest(room=room), timeout=timeout
        )

    async def rtp_forward(
        self, body: VideoRoomRtpForwardRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def stop_rtp_forward(
        self, body: VideoRoomStopRtpForwardRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def list_forwarders(
        self, body: VideoRoomListForwardersRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def join_publisher(
        self, body: PublisherJoinRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def join_subscriber(
        self, body: SubscriberJoinRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def publish(
        self,
        offer: Jsep,
        *,
        body: PublisherPublishRequest | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(
            body or PublisherPublishRequest(),
            jsep=_jsep(offer, "offer"),
            timeout=timeout,
        )

    async def configure_publisher(
        self,
        body: PublisherConfigureRequest | None = None,
        *,
        offer: Jsep | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(
            body or PublisherConfigureRequest(),
            jsep=_jsep(offer, "offer") if offer is not None else None,
            timeout=timeout,
        )

    async def join_and_configure(
        self,
        body: PublisherJoinAndConfigureRequest,
        offer: Jsep,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, jsep=_jsep(offer, "offer"), timeout=timeout)

    async def unpublish(
        self, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(PublisherUnpublishRequest(), timeout=timeout)

    async def leave(
        self, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(VideoRoomLeaveRequest(), timeout=timeout)

    async def start(
        self,
        *,
        answer: Jsep | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        """Start a subscription or resume it when no answer is supplied."""

        return await self.request(
            SubscriberStartRequest(),
            jsep=_jsep(answer, "answer") if answer is not None else None,
            timeout=timeout,
        )

    async def pause(
        self, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(SubscriberPauseRequest(), timeout=timeout)

    async def subscribe(
        self, body: SubscriberSubscribeRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def unsubscribe(
        self, body: SubscriberUnsubscribeRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def update_subscription(
        self, body: SubscriberUpdateRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def switch(
        self, body: SubscriberSwitchRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def configure_subscriber(
        self, body: SubscriberConfigureRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def add_remote_publisher(
        self, body: AddRemotePublisherRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def update_remote_publisher(
        self, body: UpdateRemotePublisherRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def remove_remote_publisher(
        self, body: RemoveRemotePublisherRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def publish_remotely(
        self, body: PublishRemotelyRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def unpublish_remotely(
        self, body: UnpublishRemotelyRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)

    async def list_remotes(
        self, body: ListRemotesRequest, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self.request(body, timeout=timeout)
