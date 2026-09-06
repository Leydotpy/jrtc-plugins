"""Wire models and response parser for the Janus VideoRoom plugin.

Outbound models inherit ``StrictBaseModel`` and intentionally avoid copying
Janus's server defaults into client requests. Inbound models inherit
``LooseBaseModel`` so additive server changes are retained, not rejected.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Any, Generic, Literal, TypeAlias, TypeVar

from jrtc.models.base import Jsep
from jrtc.models.common import JanusId, LooseBaseModel, StrictBaseModel
from pydantic import BaseModel, Field, StringConstraints, ValidationError, model_validator

from .errors import VideoRoomJanusError, VideoRoomPluginError, VideoRoomProtocolError

JsonObject: TypeAlias = dict[str, Any]  # noqa: UP040 - preserve public runtime alias
RemoteId: TypeAlias = Annotated[  # noqa: UP040 - preserve public runtime alias
    str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)
]
MediaType: TypeAlias = Literal["audio", "video", "data"]  # noqa: UP040
HostFamily: TypeAlias = Literal["ipv4", "ipv6"]  # noqa: UP040
SrtpSuite: TypeAlias = Literal[32, 80]  # noqa: UP040


class AudioCodec(StrEnum):
    OPUS = "opus"
    G722 = "g722"
    PCMU = "pcmu"
    PCMA = "pcma"
    ISAC32 = "isac32"
    ISAC16 = "isac16"


class VideoCodec(StrEnum):
    VP8 = "vp8"
    VP9 = "vp9"
    AV1 = "av1"
    H264 = "h264"
    H265 = "h265"


class DummyStream(StrictBaseModel):
    codec: VideoCodec
    fmtp: str | None = None


class VideoRoomCreateRequest(StrictBaseModel):
    """Create a room while leaving omitted defaults under server control."""

    request: Literal["create"] = "create"
    room: JanusId | None = None
    permanent: bool | None = None
    description: str | None = None
    secret: str | None = None
    pin: str | None = None
    is_private: bool | None = None
    allowed: list[str] | None = None
    require_pvtid: bool | None = None
    signed_tokens: bool | None = None
    publishers: int | None = Field(default=None, gt=0)
    bitrate: int | None = Field(default=None, gt=0)
    bitrate_cap: bool | None = None
    fir_freq: int | None = Field(default=None, ge=0)
    audiocodec: str | None = Field(default=None, min_length=1)
    videocodec: str | None = Field(default=None, min_length=1)
    vp9_profile: str | None = None
    h264_profile: str | None = None
    opus_fec: bool | None = None
    opus_dtx: bool | None = None
    audiolevel_ext: bool | None = None
    audiolevel_event: bool | None = None
    audio_active_packets: int | None = Field(default=None, gt=0)
    audio_level_average: int | None = Field(default=None, ge=0, le=127)
    videoorient_ext: bool | None = None
    playoutdelay_ext: bool | None = None
    transport_wide_cc_ext: bool | None = None
    record: bool | None = None
    rec_dir: str | None = None
    lock_record: bool | None = None
    notify_joining: bool | None = None
    require_e2ee: bool | None = None
    dummy_publisher: bool | None = None
    dummy_streams: list[DummyStream] | None = None
    threads: int | None = Field(default=None, ge=0)
    admin_key: str | None = None

    @model_validator(mode="after")
    def _dummy_streams_require_publisher(self) -> VideoRoomCreateRequest:
        if self.dummy_streams is not None and self.dummy_publisher is not True:
            raise ValueError("dummy_streams requires dummy_publisher=True")
        return self


class VideoRoomEditRequest(StrictBaseModel):
    """Only properties documented as mutable by VideoRoom are exposed."""

    request: Literal["edit"] = "edit"
    room: JanusId
    secret: str | None = None
    new_description: str | None = None
    new_secret: str | None = None
    new_pin: str | None = None
    new_is_private: bool | None = None
    new_require_pvtid: bool | None = None
    new_bitrate: int | None = Field(default=None, gt=0)
    new_fir_freq: int | None = Field(default=None, ge=0)
    new_publishers: int | None = Field(default=None, gt=0)
    new_lock_record: bool | None = None
    new_rec_dir: str | None = None
    permanent: bool | None = None


class VideoRoomDestroyRequest(StrictBaseModel):
    request: Literal["destroy"] = "destroy"
    room: JanusId
    secret: str | None = None
    permanent: bool | None = None


class VideoRoomExistsRequest(StrictBaseModel):
    request: Literal["exists"] = "exists"
    room: JanusId


class VideoRoomAllowedRequest(StrictBaseModel):
    request: Literal["allowed"] = "allowed"
    room: JanusId
    action: Literal["enable", "disable", "add", "remove"]
    secret: str | None = None
    allowed: list[str] | None = None

    @model_validator(mode="after")
    def _tokens_match_action(self) -> VideoRoomAllowedRequest:
        if self.action in {"add", "remove"} and self.allowed is None:
            raise ValueError("allowed is required for add and remove actions")
        if self.action in {"enable", "disable"} and self.allowed is not None:
            raise ValueError("allowed is only valid for add and remove actions")
        return self


class VideoRoomKickRequest(StrictBaseModel):
    request: Literal["kick"] = "kick"
    room: JanusId
    id: JanusId
    secret: str | None = None


class VideoRoomModerateRequest(StrictBaseModel):
    request: Literal["moderate"] = "moderate"
    room: JanusId
    id: JanusId
    mid: str = Field(min_length=1)
    mute: bool
    secret: str | None = None


class VideoRoomEnableRecordingRequest(StrictBaseModel):
    request: Literal["enable_recording"] = "enable_recording"
    room: JanusId
    record: bool
    secret: str | None = None


class VideoRoomListRequest(StrictBaseModel):
    request: Literal["list"] = "list"
    admin_key: str | None = None


class VideoRoomListParticipantsRequest(StrictBaseModel):
    request: Literal["listparticipants"] = "listparticipants"
    room: JanusId


class RtpForwardStream(StrictBaseModel):
    mid: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    host: str | None = Field(default=None, min_length=1)
    host_family: HostFamily | None = None
    ssrc: int | None = Field(default=None, ge=1)
    pt: int | None = Field(default=None, ge=0, le=127)
    rtcp_port: int | None = Field(default=None, ge=1, le=65535)
    simulcast: bool | None = None
    port_2: int | None = Field(default=None, ge=1, le=65535)
    ssrc_2: int | None = Field(default=None, ge=1)
    pt_2: int | None = Field(default=None, ge=0, le=127)
    port_3: int | None = Field(default=None, ge=1, le=65535)
    ssrc_3: int | None = Field(default=None, ge=1)
    pt_3: int | None = Field(default=None, ge=0, le=127)

    @model_validator(mode="after")
    def _simulcast_mode(self) -> RtpForwardStream:
        separate_layers = any(
            value is not None
            for value in (
                self.port_2,
                self.ssrc_2,
                self.pt_2,
                self.port_3,
                self.ssrc_3,
                self.pt_3,
            )
        )
        if self.simulcast is True and separate_layers:
            raise ValueError("simulcast=True cannot be combined with separate layer targets")
        if any(value is not None for value in (self.ssrc_2, self.pt_2)) and self.port_2 is None:
            raise ValueError("port_2 is required for second-layer SSRC or payload type")
        if any(value is not None for value in (self.ssrc_3, self.pt_3)) and self.port_3 is None:
            raise ValueError("port_3 is required for third-layer SSRC or payload type")
        return self


class VideoRoomRtpForwardRequest(StrictBaseModel):
    request: Literal["rtp_forward"] = "rtp_forward"
    room: JanusId
    publisher_id: JanusId
    streams: list[RtpForwardStream] = Field(min_length=1)
    host: str | None = Field(default=None, min_length=1)
    host_family: HostFamily | None = None
    srtp_suite: SrtpSuite | None = None
    srtp_crypto: str | None = None
    admin_key: str | None = None

    @model_validator(mode="after")
    def _targets_and_srtp(self) -> VideoRoomRtpForwardRequest:
        if self.host is None and any(stream.host is None for stream in self.streams):
            raise ValueError("each stream needs host when the request has no global host")
        if (self.srtp_suite is None) != (self.srtp_crypto is None):
            raise ValueError("srtp_suite and srtp_crypto must be provided together")
        return self


class VideoRoomStopRtpForwardRequest(StrictBaseModel):
    request: Literal["stop_rtp_forward"] = "stop_rtp_forward"
    room: JanusId
    publisher_id: JanusId
    stream_id: JanusId


class VideoRoomListForwardersRequest(StrictBaseModel):
    request: Literal["listforwarders"] = "listforwarders"
    room: JanusId
    secret: str | None = None


class SubscribeTarget(StrictBaseModel):
    """A publisher source to add to a subscription."""

    feed: JanusId
    mid: str | None = None
    crossrefid: str | None = None
    send: bool | None = None
    substream: int | None = Field(default=None, ge=0, le=2)
    temporal: int | None = Field(default=None, ge=0, le=2)
    fallback: int | None = Field(default=None, ge=0)
    spatial_layer: int | None = Field(default=None, ge=0, le=2)
    temporal_layer: int | None = Field(default=None, ge=0, le=2)


class UnsubscribeTarget(StrictBaseModel):
    """A source or subscriber m-line to remove from a subscription."""

    feed: JanusId | None = None
    mid: str | None = None
    sub_mid: str | None = None

    @model_validator(mode="after")
    def _addressed(self) -> UnsubscribeTarget:
        if self.feed is None and self.sub_mid is None:
            raise ValueError("unsubscribe target requires feed or sub_mid")
        if self.mid is not None and self.feed is None:
            raise ValueError("mid requires feed in an unsubscribe target")
        return self


class SwitchTarget(StrictBaseModel):
    """Map one existing subscriber m-line to a new publisher source."""

    feed: JanusId
    mid: str = Field(min_length=1)
    sub_mid: str = Field(min_length=1)
    substream: int | None = Field(default=None, ge=0, le=2)
    temporal: int | None = Field(default=None, ge=0, le=2)
    fallback: int | None = Field(default=None, ge=0)
    spatial_layer: int | None = Field(default=None, ge=0, le=2)
    temporal_layer: int | None = Field(default=None, ge=0, le=2)


class PublisherJoinRequest(StrictBaseModel):
    request: Literal["join"] = "join"
    ptype: Literal["publisher"] = "publisher"
    room: JanusId
    id: JanusId | None = None
    display: str | None = None
    token: str | None = None
    pin: str | None = None
    metadata: JsonObject | None = None


class SubscriberJoinRequest(StrictBaseModel):
    request: Literal["join"] = "join"
    ptype: Literal["subscriber"] = "subscriber"
    room: JanusId
    private_id: JanusId | None = None
    pin: str | None = None
    use_msid: bool | None = None
    autoupdate: bool | None = None
    streams: list[SubscribeTarget] | None = Field(default=None, min_length=1)
    # Deprecated legacy selectors are retained for interoperating with older
    # Janus deployments. New code should use ``streams``.
    feed: JanusId | None = None
    audio: bool | None = None
    video: bool | None = None
    data: bool | None = None
    offer_audio: bool | None = None
    offer_video: bool | None = None
    offer_data: bool | None = None

    @model_validator(mode="after")
    def _has_source(self) -> SubscriberJoinRequest:
        if self.streams is None and self.feed is None:
            raise ValueError("subscriber join requires streams or the legacy feed")
        return self


class StreamDescription(StrictBaseModel):
    mid: str = Field(min_length=1)
    description: str


class PublisherStreamControl(StrictBaseModel):
    mid: str = Field(min_length=1)
    keyframe: bool | None = None
    send: bool | None = None
    min_delay: int | None = Field(default=None, ge=0)
    max_delay: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _delay_order(self) -> PublisherStreamControl:
        if (
            self.min_delay is not None
            and self.max_delay is not None
            and self.min_delay > self.max_delay
        ):
            raise ValueError("min_delay cannot exceed max_delay")
        return self


class PublisherPublishRequest(StrictBaseModel):
    request: Literal["publish"] = "publish"
    audiocodec: AudioCodec | None = None
    videocodec: VideoCodec | None = None
    bitrate: int | None = Field(default=None, ge=0)
    record: bool | None = None
    filename: str | None = None
    display: str | None = None
    metadata: JsonObject | None = None
    audio_level_average: int | None = Field(default=None, ge=0, le=127)
    audio_active_packets: int | None = Field(default=None, gt=0)
    descriptions: list[StreamDescription] | None = None


class PublisherConfigureRequest(StrictBaseModel):
    request: Literal["configure"] = "configure"
    audiocodec: AudioCodec | None = None
    videocodec: VideoCodec | None = None
    bitrate: int | None = Field(default=None, ge=0)
    keyframe: bool | None = None
    record: bool | None = None
    filename: str | None = None
    display: str | None = None
    metadata: JsonObject | None = None
    audio_level_average: int | None = Field(default=None, ge=0, le=127)
    audio_active_packets: int | None = Field(default=None, gt=0)
    streams: list[PublisherStreamControl] | None = None
    descriptions: list[StreamDescription] | None = None


class PublisherJoinAndConfigureRequest(StrictBaseModel):
    request: Literal["joinandconfigure"] = "joinandconfigure"
    ptype: Literal["publisher"] = "publisher"
    room: JanusId
    id: JanusId | None = None
    display: str | None = None
    token: str | None = None
    pin: str | None = None
    metadata: JsonObject | None = None
    audiocodec: AudioCodec | None = None
    videocodec: VideoCodec | None = None
    bitrate: int | None = Field(default=None, ge=0)
    record: bool | None = None
    filename: str | None = None
    audio_level_average: int | None = Field(default=None, ge=0, le=127)
    audio_active_packets: int | None = Field(default=None, gt=0)
    descriptions: list[StreamDescription] | None = None


class PublisherUnpublishRequest(StrictBaseModel):
    request: Literal["unpublish"] = "unpublish"


class VideoRoomLeaveRequest(StrictBaseModel):
    request: Literal["leave"] = "leave"


class SubscriberStartRequest(StrictBaseModel):
    request: Literal["start"] = "start"


class SubscriberPauseRequest(StrictBaseModel):
    request: Literal["pause"] = "pause"


class SubscriberSubscribeRequest(StrictBaseModel):
    request: Literal["subscribe"] = "subscribe"
    streams: list[SubscribeTarget] = Field(min_length=1)


class SubscriberUnsubscribeRequest(StrictBaseModel):
    request: Literal["unsubscribe"] = "unsubscribe"
    streams: list[UnsubscribeTarget] = Field(min_length=1)


class SubscriberUpdateRequest(StrictBaseModel):
    request: Literal["update"] = "update"
    subscribe: list[SubscribeTarget] | None = Field(default=None, min_length=1)
    unsubscribe: list[UnsubscribeTarget] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _has_change(self) -> SubscriberUpdateRequest:
        if self.subscribe is None and self.unsubscribe is None:
            raise ValueError("update requires subscribe, unsubscribe, or both")
        return self


class SubscriberSwitchRequest(StrictBaseModel):
    request: Literal["switch"] = "switch"
    streams: list[SwitchTarget] = Field(min_length=1)


class SubscriberStreamControl(StrictBaseModel):
    mid: str = Field(min_length=1)
    send: bool | None = None
    substream: int | None = Field(default=None, ge=0, le=2)
    temporal: int | None = Field(default=None, ge=0, le=2)
    fallback: int | None = Field(default=None, ge=0)
    spatial_layer: int | None = Field(default=None, ge=0, le=2)
    temporal_layer: int | None = Field(default=None, ge=0, le=2)
    audio_level_average: int | None = Field(default=None, ge=0, le=127)
    audio_active_packets: int | None = Field(default=None, gt=0)
    min_delay: int | None = Field(default=None, ge=0)
    max_delay: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _delay_order(self) -> SubscriberStreamControl:
        if (
            self.min_delay is not None
            and self.max_delay is not None
            and self.min_delay > self.max_delay
        ):
            raise ValueError("min_delay cannot exceed max_delay")
        return self


class SubscriberConfigureRequest(StrictBaseModel):
    request: Literal["configure"] = "configure"
    streams: list[SubscriberStreamControl] | None = Field(default=None, min_length=1)
    restart: bool | None = None

    @model_validator(mode="after")
    def _has_operation(self) -> SubscriberConfigureRequest:
        if self.streams is None and self.restart is not True:
            raise ValueError("configure requires stream controls or restart=True")
        return self


class RemotePublisherStream(StrictBaseModel):
    type: MediaType
    mindex: int = Field(ge=0)
    mid: str = Field(min_length=1)
    disabled: bool | None = None
    codec: str | None = None
    description: str | None = None
    stereo: bool | None = None
    fec: bool | None = None
    dtx: bool | None = None
    h264_profile: str | None = Field(default=None, alias="h264-profile")
    vp9_profile: str | None = Field(default=None, alias="vp9-profile")
    simulcast: bool | None = None
    svc: bool | None = None
    audiolevel_ext_id: int | None = Field(default=None, ge=1)
    videoorient_ext_id: int | None = Field(default=None, ge=1)
    playoutdelay_ext_id: int | None = Field(default=None, ge=1)


class AddRemotePublisherRequest(StrictBaseModel):
    request: Literal["add_remote_publisher"] = "add_remote_publisher"
    room: JanusId
    streams: list[RemotePublisherStream] = Field(min_length=1)
    id: JanusId | None = None
    secret: str | None = None
    display: str | None = None
    mcast: str | None = None
    iface: str | None = None
    port: int | None = Field(default=None, ge=0, le=65535)
    srtp_suite: SrtpSuite | None = None
    srtp_crypto: str | None = None

    @model_validator(mode="after")
    def _complete_srtp(self) -> AddRemotePublisherRequest:
        if (self.srtp_suite is None) != (self.srtp_crypto is None):
            raise ValueError("srtp_suite and srtp_crypto must be provided together")
        return self


class UpdateRemotePublisherRequest(StrictBaseModel):
    request: Literal["update_remote_publisher"] = "update_remote_publisher"
    room: JanusId
    id: JanusId
    secret: str | None = None
    display: str | None = None
    metadata: JsonObject | None = None
    srtp_suite: SrtpSuite | None = None
    srtp_crypto: str | None = None
    streams: list[RemotePublisherStream] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _complete_srtp(self) -> UpdateRemotePublisherRequest:
        if (self.srtp_suite is None) != (self.srtp_crypto is None):
            raise ValueError("srtp_suite and srtp_crypto must be provided together")
        return self


class RemoveRemotePublisherRequest(StrictBaseModel):
    request: Literal["remove_remote_publisher"] = "remove_remote_publisher"
    room: JanusId
    id: JanusId
    secret: str | None = None


class PublishRemotelyRequest(StrictBaseModel):
    request: Literal["publish_remotely"] = "publish_remotely"
    room: JanusId
    publisher_id: JanusId
    remote_id: RemoteId
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    secret: str | None = None
    host_family: HostFamily | None = None
    rtcp_port: int | None = Field(default=None, ge=1, le=65535)
    srtp_suite: SrtpSuite | None = None
    srtp_crypto: str | None = None

    @model_validator(mode="after")
    def _complete_srtp(self) -> PublishRemotelyRequest:
        if (self.srtp_suite is None) != (self.srtp_crypto is None):
            raise ValueError("srtp_suite and srtp_crypto must be provided together")
        return self


class UnpublishRemotelyRequest(StrictBaseModel):
    request: Literal["unpublish_remotely"] = "unpublish_remotely"
    room: JanusId
    publisher_id: JanusId
    remote_id: RemoteId
    secret: str | None = None


class ListRemotesRequest(StrictBaseModel):
    request: Literal["list_remotes"] = "list_remotes"
    room: JanusId
    publisher_id: JanusId
    secret: str | None = None


VideoRoomRequest: TypeAlias = (  # noqa: UP040 - preserve public runtime alias
    VideoRoomCreateRequest
    | VideoRoomEditRequest
    | VideoRoomDestroyRequest
    | VideoRoomExistsRequest
    | VideoRoomAllowedRequest
    | VideoRoomKickRequest
    | VideoRoomModerateRequest
    | VideoRoomEnableRecordingRequest
    | VideoRoomListRequest
    | VideoRoomListParticipantsRequest
    | VideoRoomRtpForwardRequest
    | VideoRoomStopRtpForwardRequest
    | VideoRoomListForwardersRequest
    | PublisherJoinRequest
    | SubscriberJoinRequest
    | PublisherPublishRequest
    | PublisherConfigureRequest
    | PublisherJoinAndConfigureRequest
    | PublisherUnpublishRequest
    | VideoRoomLeaveRequest
    | SubscriberStartRequest
    | SubscriberPauseRequest
    | SubscriberSubscribeRequest
    | SubscriberUnsubscribeRequest
    | SubscriberUpdateRequest
    | SubscriberSwitchRequest
    | SubscriberConfigureRequest
    | AddRemotePublisherRequest
    | UpdateRemotePublisherRequest
    | RemoveRemotePublisherRequest
    | PublishRemotelyRequest
    | UnpublishRemotelyRequest
    | ListRemotesRequest
)


class VideoRoomSummary(LooseBaseModel):
    room: JanusId
    description: str | None = None
    pin_required: bool | None = None
    is_private: bool | None = None
    max_publishers: int | None = None
    bitrate: int | None = None
    bitrate_cap: bool | None = None
    fir_freq: int | None = None
    require_pvtid: bool | None = None
    require_e2ee: bool | None = None
    dummy_publisher: bool | None = None
    notify_joining: bool | None = None
    audiocodec: str | None = None
    videocodec: str | None = None
    opus_fec: bool | None = None
    opus_dtx: bool | None = None
    record: bool | None = None
    rec_dir: str | None = None
    lock_record: bool | None = None
    num_participants: int | None = None
    audiolevel_ext: bool | None = None
    audiolevel_event: bool | None = None
    audio_active_packets: int | None = None
    audio_level_average: int | None = None
    videoorient_ext: bool | None = None
    playoutdelay_ext: bool | None = None
    transport_wide_cc_ext: bool | None = None


class VideoRoomParticipant(LooseBaseModel):
    id: JanusId
    display: str | None = None
    metadata: JsonObject | None = None
    publisher: bool
    talking: bool | None = None


class PublisherStreamInfo(LooseBaseModel):
    type: MediaType
    mindex: int | None = None
    mid: str | None = None
    disabled: bool | None = None
    codec: str | None = None
    description: str | None = None
    moderated: bool | None = None
    stereo: bool | None = None
    fec: bool | None = None
    dtx: bool | None = None
    h264_profile: str | None = Field(default=None, alias="h264-profile")
    vp9_profile: str | None = Field(default=None, alias="vp9-profile")
    simulcast: bool | None = None
    svc: bool | None = None
    talking: bool | None = None


class PublisherInfo(LooseBaseModel):
    id: JanusId
    display: str | None = None
    metadata: JsonObject | None = None
    streams: list[PublisherStreamInfo] = Field(default_factory=list)
    dummy: bool | None = None
    talking: bool | None = None


class AttendeeInfo(LooseBaseModel):
    id: JanusId
    display: str | None = None
    metadata: JsonObject | None = None


class SubscriberStreamInfo(LooseBaseModel):
    mindex: int | None = None
    mid: str | None = None
    type: MediaType
    active: bool | None = None
    feed_id: JanusId
    feed_mid: str | None = None
    feed_display: str | None = None
    send: bool | None = None
    codec: str | None = None
    h264_profile: str | None = Field(default=None, alias="h264-profile")
    vp9_profile: str | None = Field(default=None, alias="vp9-profile")
    ready: bool | None = None
    simulcast: JsonObject | None = None
    svc: JsonObject | None = None
    playout_delay: JsonObject | None = Field(default=None, alias="playout-delay")
    sources: int | None = None
    source_ids: list[JanusId] | None = None
    crossrefid: str | None = None


class ForwarderInfo(LooseBaseModel):
    stream_id: JanusId | None = None
    type: MediaType
    host: str
    port: int
    local_rtcp_port: int | None = None
    remote_rtcp_port: int | None = None
    ssrc: int | None = None
    pt: int | None = None
    substream: int | None = None
    srtp: bool | None = None


class PublisherForwarders(LooseBaseModel):
    publisher_id: JanusId
    forwarders: list[ForwarderInfo]


class RemotePublicationInfo(LooseBaseModel):
    remote_id: RemoteId
    host: str
    port: int
    rtcp_port: int | None = None


class VideoRoomCreated(LooseBaseModel):
    videoroom: Literal["created"]
    room: JanusId
    permanent: bool


class VideoRoomEdited(LooseBaseModel):
    videoroom: Literal["edited"]
    room: JanusId


class VideoRoomDestroyed(LooseBaseModel):
    videoroom: Literal["destroyed"]
    room: JanusId


class VideoRoomSuccess(LooseBaseModel):
    videoroom: Literal["success"]
    room: JanusId | None = None
    permanent: bool | None = None
    exists: bool | None = None
    allowed: list[str] | None = None
    id: JanusId | None = None
    ip: str | None = None
    port: int | None = None
    rtcp_port: int | None = None
    remote_id: RemoteId | None = None


class VideoRoomList(LooseBaseModel):
    videoroom: Literal["success"]
    rooms: list[VideoRoomSummary] = Field(alias="list")


class VideoRoomParticipants(LooseBaseModel):
    videoroom: Literal["participants"]
    room: JanusId
    participants: list[VideoRoomParticipant]


class VideoRoomJoined(LooseBaseModel):
    videoroom: Literal["joined"]
    room: JanusId
    description: str | None = None
    id: JanusId
    private_id: JanusId | None = None
    publishers: list[PublisherInfo] = Field(default_factory=list)
    attendees: list[AttendeeInfo] = Field(default_factory=list)


class VideoRoomPublisherEvent(LooseBaseModel):
    videoroom: Literal["event"]
    room: JanusId
    publishers: list[PublisherInfo]


class VideoRoomJoiningEvent(LooseBaseModel):
    videoroom: Literal["event"]
    room: JanusId
    joining: AttendeeInfo


class VideoRoomUnpublishedEvent(LooseBaseModel):
    videoroom: Literal["event"]
    room: JanusId | None = None
    unpublished: JanusId | Literal["ok"]


class VideoRoomLeavingEvent(LooseBaseModel):
    videoroom: Literal["event"]
    room: JanusId | None = None
    leaving: JanusId | Literal["ok"]
    display: str | None = None


class VideoRoomConfiguredEvent(LooseBaseModel):
    videoroom: Literal["event"]
    configured: Literal["ok"]
    room: JanusId | None = None


class VideoRoomRtpForwarded(LooseBaseModel):
    videoroom: Literal["rtp_forward"]
    room: JanusId
    publisher_id: JanusId
    forwarders: list[ForwarderInfo]


class VideoRoomRtpForwardStopped(LooseBaseModel):
    videoroom: Literal["stop_rtp_forward"]
    room: JanusId
    publisher_id: JanusId
    stream_id: JanusId


class VideoRoomForwarders(LooseBaseModel):
    videoroom: Literal["forwarders"]
    room: JanusId
    publishers: list[PublisherForwarders]


class VideoRoomAttached(LooseBaseModel):
    videoroom: Literal["attached"]
    room: JanusId
    streams: list[SubscriberStreamInfo]


class VideoRoomStartedEvent(LooseBaseModel):
    videoroom: Literal["event"]
    started: Literal["ok"]
    room: JanusId | None = None


class VideoRoomPausedEvent(LooseBaseModel):
    videoroom: Literal["event"]
    paused: Literal["ok"]
    room: JanusId | None = None


class VideoRoomLeftEvent(LooseBaseModel):
    videoroom: Literal["event"]
    left: Literal["ok"]
    room: JanusId | None = None


class VideoRoomUpdated(LooseBaseModel):
    videoroom: Literal["updated"]
    room: JanusId
    streams: list[SubscriberStreamInfo] | None = None


class VideoRoomSwitchedEvent(LooseBaseModel):
    videoroom: Literal["event"]
    switched: Literal["ok"]
    room: JanusId
    changes: int
    streams: list[SubscriberStreamInfo] | None = None


class VideoRoomUpdatingEvent(LooseBaseModel):
    videoroom: Literal["event"]
    updating: Any
    room: JanusId | None = None


class VideoRoomTalkingEvent(LooseBaseModel):
    videoroom: Literal["talking", "stopped-talking"]
    room: JanusId
    id: JanusId
    audio_level_dbov_avg: int = Field(alias="audio-level-dBov-avg")


class VideoRoomRemotes(LooseBaseModel):
    videoroom: Literal["success"]
    room: JanusId
    id: JanusId
    remotes: list[RemotePublicationInfo] = Field(alias="list")


class VideoRoomEvent(LooseBaseModel):
    """A known ``event`` whose optional detail is not one fixed variant."""

    videoroom: Literal["event"]
    room: JanusId | None = None


class UnknownVideoRoomResponse(LooseBaseModel):
    """A future response retained without weakening outbound validation."""

    videoroom: str | None = None


VideoRoomResponse: TypeAlias = (  # noqa: UP040 - preserve public runtime alias
    VideoRoomCreated
    | VideoRoomEdited
    | VideoRoomDestroyed
    | VideoRoomSuccess
    | VideoRoomList
    | VideoRoomParticipants
    | VideoRoomJoined
    | VideoRoomPublisherEvent
    | VideoRoomJoiningEvent
    | VideoRoomUnpublishedEvent
    | VideoRoomLeavingEvent
    | VideoRoomConfiguredEvent
    | VideoRoomRtpForwarded
    | VideoRoomRtpForwardStopped
    | VideoRoomForwarders
    | VideoRoomAttached
    | VideoRoomStartedEvent
    | VideoRoomPausedEvent
    | VideoRoomLeftEvent
    | VideoRoomUpdated
    | VideoRoomSwitchedEvent
    | VideoRoomUpdatingEvent
    | VideoRoomTalkingEvent
    | VideoRoomRemotes
    | VideoRoomEvent
    | UnknownVideoRoomResponse
)
ResponseT = TypeVar("ResponseT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class VideoRoomReply(Generic[ResponseT]):  # noqa: UP046 - preserve public generic API
    """Typed plugin data plus metadata from the surrounding Janus event."""

    data: ResponseT
    jsep: Jsep | None = None
    transaction: str | None = None
    raw: Any = field(default=None, repr=False, compare=False)


def _mapping(value: Any, *, context: str) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", by_alias=True, exclude_none=False)
    if isinstance(value, Mapping):
        return dict(value)
    raise VideoRoomProtocolError(f"{context} must be a mapping or Pydantic model")


def _event_model(data: dict[str, Any]) -> type[BaseModel]:
    for field_name, model in (
        ("publishers", VideoRoomPublisherEvent),
        ("joining", VideoRoomJoiningEvent),
        ("configured", VideoRoomConfiguredEvent),
        ("unpublished", VideoRoomUnpublishedEvent),
        ("leaving", VideoRoomLeavingEvent),
        ("started", VideoRoomStartedEvent),
        ("paused", VideoRoomPausedEvent),
        ("left", VideoRoomLeftEvent),
        ("switched", VideoRoomSwitchedEvent),
        ("updating", VideoRoomUpdatingEvent),
    ):
        if field_name in data:
            return model
    return VideoRoomEvent


def parse_videoroom_response(payload: Any) -> VideoRoomReply[VideoRoomResponse]:
    """Parse a core Janus response or a bare VideoRoom plugin-data object."""

    outer = _mapping(payload, context="response")
    transaction = outer.get("transaction")
    jsep_payload: Any = None

    if "janus" in outer:
        if outer.get("janus") == "error":
            error = _mapping(outer.get("error"), context="Janus error")
            raise VideoRoomJanusError(
                int(error.get("code", -1)),
                str(error.get("reason", "unknown Janus error")),
                transaction=transaction,
            )
        plugin_data = _mapping(outer.get("plugindata"), context="plugindata")
        plugin = plugin_data.get("plugin")
        if plugin != "janus.plugin.videoroom":
            raise VideoRoomProtocolError(f"expected janus.plugin.videoroom, received {plugin!r}")
        data = _mapping(plugin_data.get("data"), context="plugin data")
        jsep_payload = outer.get("jsep")
    else:
        data = outer

    if "error_code" in data or "error" in data:
        raise VideoRoomPluginError(
            int(data.get("error_code", -1)),
            str(data.get("error", "unknown VideoRoom error")),
            transaction=transaction,
            raw=data,
        )

    kind = data.get("videoroom")
    models: dict[str, type[BaseModel]] = {
        "created": VideoRoomCreated,
        "edited": VideoRoomEdited,
        "destroyed": VideoRoomDestroyed,
        "participants": VideoRoomParticipants,
        "joined": VideoRoomJoined,
        "rtp_forward": VideoRoomRtpForwarded,
        "stop_rtp_forward": VideoRoomRtpForwardStopped,
        "forwarders": VideoRoomForwarders,
        "attached": VideoRoomAttached,
        "updated": VideoRoomUpdated,
        "talking": VideoRoomTalkingEvent,
        "stopped-talking": VideoRoomTalkingEvent,
    }
    model: type[BaseModel]
    if kind == "event":
        model = _event_model(data)
    elif kind == "success" and "list" in data:
        model = VideoRoomRemotes if "id" in data else VideoRoomList
    elif kind == "success":
        model = VideoRoomSuccess
    else:
        model = models.get(str(kind), UnknownVideoRoomResponse)

    try:
        parsed = model.model_validate(data)
        jsep = Jsep.model_validate(jsep_payload) if jsep_payload is not None else None
    except ValidationError as exc:
        raise VideoRoomProtocolError("invalid VideoRoom response") from exc
    return VideoRoomReply(data=parsed, jsep=jsep, transaction=transaction, raw=payload)
