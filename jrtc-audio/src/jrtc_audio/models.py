"""Strict request models and forward-compatible AudioBridge replies.

The classes in the first half of this module model plugin message bodies, not
the surrounding Janus ``message`` envelope.  They deliberately have no server
defaults: fields a caller does not set stay off the wire.  Response classes use
``LooseBaseModel`` because Janus may add fields in a compatible release.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, Field, ValidationError, model_validator

from jrtc.models.base import Jsep
from jrtc.models.common import JanusId, LooseBaseModel, StrictBaseModel

from .errors import (
    AudioBridgeJanusError,
    AudioBridgePluginError,
    AudioBridgeProtocolError,
)

RoomId: TypeAlias = JanusId
ParticipantId: TypeAlias = JanusId
StreamId: TypeAlias = JanusId
AudioCodec: TypeAlias = Literal["opus", "pcma", "pcmu"]
HostFamily: TypeAlias = Literal["ipv4", "ipv6"]
SrtpSuite: TypeAlias = Literal[32, 80]


class AudioBridgeRtpTransport(StrictBaseModel):
    """Plain-RTP participant transport.

    An empty object is meaningful: it creates a send-only participant or asks
    Janus for its RTP endpoint first when ``generate_offer`` is used.  If one
    endpoint field is supplied, both are required.
    """

    ip: str | None = Field(default=None, min_length=1)
    port: int | None = Field(default=None, ge=1, le=65535)
    payload_type: int | None = Field(default=None, ge=0, le=127)
    audiolevel_ext: int | None = Field(default=None, ge=1, le=255)
    fec: bool | None = None

    @model_validator(mode="after")
    def _complete_endpoint(self) -> "AudioBridgeRtpTransport":
        if (self.ip is None) != (self.port is None):
            raise ValueError("ip and port must be provided together, or both omitted")
        return self


class AudioBridgeCreateRequest(StrictBaseModel):
    """Create a dynamic room; all Janus defaults remain server-owned."""

    request: Literal["create"] = "create"
    room: RoomId | None = Field(default=None, ge=1)
    permanent: bool | None = None
    description: str | None = None
    secret: str | None = None
    pin: str | None = None
    is_private: bool | None = None
    allowed: list[str] | None = None
    sampling_rate: int | None = Field(default=None, gt=0)
    spatial_audio: bool | None = None
    audiolevel_ext: bool | None = None
    audiolevel_event: bool | None = None
    audio_active_packets: int | None = Field(default=None, gt=0)
    audio_level_average: int | None = Field(default=None, ge=0, le=127)
    default_expectedloss: int | None = Field(default=None, ge=0, le=20)
    default_bitrate: int | None = Field(default=None, ge=0)
    denoise: bool | None = None
    record: bool | None = None
    record_file: str | None = None
    record_dir: str | None = None
    mjrs: bool | None = None
    mjrs_dir: str | None = None
    allow_rtp_participants: bool | None = None
    groups: list[str] | None = None
    admin_key: str | None = None


class AudioBridgeEditRequest(StrictBaseModel):
    """Edit the subset of room properties Janus declares mutable."""

    request: Literal["edit"] = "edit"
    room: RoomId = Field(ge=1)
    secret: str | None = None
    new_description: str | None = None
    new_secret: str | None = None
    new_pin: str | None = None
    new_is_private: bool | None = None
    new_record_dir: str | None = None
    new_mjrs_dir: str | None = None
    permanent: bool | None = None


class AudioBridgeDestroyRequest(StrictBaseModel):
    request: Literal["destroy"] = "destroy"
    room: RoomId = Field(ge=1)
    secret: str | None = None
    permanent: bool | None = None


class AudioBridgeEnableRecordingRequest(StrictBaseModel):
    """Toggle mixed WAV recording (not per-participant MJR recording)."""

    request: Literal["enable_recording"] = "enable_recording"
    room: RoomId = Field(ge=1)
    secret: str | None = None
    record: bool
    record_file: str | None = None
    record_dir: str | None = None


class AudioBridgeEnableMjrsRequest(StrictBaseModel):
    """Toggle MJR recording for every participant in a room."""

    request: Literal["enable_mjrs"] = "enable_mjrs"
    room: RoomId = Field(ge=1)
    secret: str | None = None
    mjrs: bool
    mjrs_dir: str | None = None


class AudioBridgeExistsRequest(StrictBaseModel):
    request: Literal["exists"] = "exists"
    room: RoomId = Field(ge=1)


class AudioBridgeAllowedRequest(StrictBaseModel):
    request: Literal["allowed"] = "allowed"
    room: RoomId = Field(ge=1)
    action: Literal["enable", "disable", "add", "remove"]
    secret: str | None = None
    allowed: list[str] | None = None

    @model_validator(mode="after")
    def _tokens_for_mutation(self) -> "AudioBridgeAllowedRequest":
        if self.action in {"add", "remove"} and self.allowed is None:
            raise ValueError("allowed is required for add and remove actions")
        if self.action in {"enable", "disable"} and self.allowed is not None:
            raise ValueError("allowed is only valid for add and remove actions")
        return self


class AudioBridgeKickRequest(StrictBaseModel):
    request: Literal["kick"] = "kick"
    room: RoomId = Field(ge=1)
    id: ParticipantId = Field(ge=1)
    secret: str | None = None


class AudioBridgeKickAllRequest(StrictBaseModel):
    request: Literal["kick_all"] = "kick_all"
    room: RoomId = Field(ge=1)
    secret: str | None = None


class AudioBridgeSuspendRequest(StrictBaseModel):
    request: Literal["suspend"] = "suspend"
    room: RoomId = Field(ge=1)
    id: ParticipantId = Field(ge=1)
    secret: str | None = None
    pause_events: bool | None = None
    stop_record: bool | None = None


class AudioBridgeResumeRequest(StrictBaseModel):
    request: Literal["resume"] = "resume"
    room: RoomId = Field(ge=1)
    id: ParticipantId = Field(ge=1)
    secret: str | None = None
    record: bool | None = None
    filename: str | None = None


class AudioBridgeListRequest(StrictBaseModel):
    request: Literal["list"] = "list"


class AudioBridgeListParticipantsRequest(StrictBaseModel):
    request: Literal["listparticipants"] = "listparticipants"
    room: RoomId = Field(ge=1)


class AudioBridgeResetDecoderRequest(StrictBaseModel):
    """Reset the Opus decoder for the participant bound to this handle."""

    request: Literal["resetdecoder"] = "resetdecoder"


class AudioBridgeParticipantAdminRequest(StrictBaseModel):
    """Shared body for per-participant admin operations."""

    room: RoomId = Field(ge=1)
    id: ParticipantId = Field(ge=1)
    secret: str | None = None


class AudioBridgeMuteRequest(AudioBridgeParticipantAdminRequest):
    request: Literal["mute"] = "mute"


class AudioBridgeUnmuteRequest(AudioBridgeParticipantAdminRequest):
    request: Literal["unmute"] = "unmute"


class AudioBridgeRoomAdminRequest(StrictBaseModel):
    room: RoomId = Field(ge=1)
    secret: str | None = None


class AudioBridgeMuteRoomRequest(AudioBridgeRoomAdminRequest):
    request: Literal["mute_room"] = "mute_room"


class AudioBridgeUnmuteRoomRequest(AudioBridgeRoomAdminRequest):
    request: Literal["unmute_room"] = "unmute_room"


class AudioBridgeRtpForwardRequest(StrictBaseModel):
    request: Literal["rtp_forward"] = "rtp_forward"
    room: RoomId = Field(ge=1)
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    group: str | None = None
    ssrc: int | None = Field(default=None, ge=1)
    codec: AudioCodec | None = None
    ptype: int | None = Field(default=None, ge=0, le=127)
    host_family: HostFamily | None = None
    srtp_suite: SrtpSuite | None = None
    srtp_crypto: str | None = None
    always_on: bool | None = None
    admin_key: str | None = None

    @model_validator(mode="after")
    def _complete_srtp(self) -> "AudioBridgeRtpForwardRequest":
        if (self.srtp_suite is None) != (self.srtp_crypto is None):
            raise ValueError("srtp_suite and srtp_crypto must be provided together")
        return self


class AudioBridgeStopRtpForwardRequest(StrictBaseModel):
    request: Literal["stop_rtp_forward"] = "stop_rtp_forward"
    room: RoomId = Field(ge=1)
    stream_id: StreamId


class AudioBridgeListForwardersRequest(StrictBaseModel):
    request: Literal["listforwarders"] = "listforwarders"
    room: RoomId = Field(ge=1)


class AudioBridgePlayFileRequest(StrictBaseModel):
    request: Literal["play_file"] = "play_file"
    room: RoomId = Field(ge=1)
    filename: str = Field(min_length=1)
    secret: str | None = None
    group: str | None = None
    file_id: str | None = None
    loop: bool | None = None
    admin_key: str | None = None


class AudioBridgeIsPlayingRequest(StrictBaseModel):
    request: Literal["is_playing"] = "is_playing"
    room: RoomId = Field(ge=1)
    file_id: str = Field(min_length=1)
    secret: str | None = None


class AudioBridgeListAnnouncementsRequest(StrictBaseModel):
    request: Literal["listannouncements"] = "listannouncements"
    room: RoomId = Field(ge=1)
    secret: str | None = None


class AudioBridgeStopFileRequest(StrictBaseModel):
    request: Literal["stop_file"] = "stop_file"
    room: RoomId = Field(ge=1)
    file_id: str = Field(min_length=1)
    secret: str | None = None


class AudioBridgeStopAllFilesRequest(StrictBaseModel):
    request: Literal["stop_all_files"] = "stop_all_files"
    room: RoomId = Field(ge=1)
    secret: str | None = None


class AudioBridgeJoinRequest(StrictBaseModel):
    request: Literal["join"] = "join"
    room: RoomId = Field(ge=1)
    id: ParticipantId | None = Field(default=None, ge=1)
    group: str | None = None
    pin: str | None = None
    display: str | None = None
    token: str | None = None
    muted: bool | None = None
    suspended: bool | None = None
    pause_events: bool | None = None
    codec: AudioCodec | None = None
    bitrate: int | None = Field(default=None, ge=0)
    quality: int | None = Field(default=None, ge=0, le=10)
    expected_loss: int | None = Field(default=None, ge=0, le=20)
    volume: int | None = Field(default=None, ge=0)
    spatial_position: int | None = Field(default=None, ge=0, le=100)
    denoise: bool | None = None
    secret: str | None = None
    audio_level_average: int | None = Field(default=None, ge=0, le=127)
    audio_active_packets: int | None = Field(default=None, gt=0)
    record: bool | None = None
    filename: str | None = None
    generate_offer: bool | None = None
    rtp: AudioBridgeRtpTransport | None = None


class AudioBridgeConfigureRequest(StrictBaseModel):
    """Update media settings or drive either JSEP negotiation direction."""

    request: Literal["configure"] = "configure"
    muted: bool | None = None
    display: str | None = None
    bitrate: int | None = Field(default=None, ge=0)
    quality: int | None = Field(default=None, ge=0, le=10)
    expected_loss: int | None = Field(default=None, ge=0, le=20)
    volume: int | None = Field(default=None, ge=0)
    spatial_position: int | None = Field(default=None, ge=0, le=100)
    denoise: bool | None = None
    record: bool | None = None
    filename: str | None = None
    group: str | None = None
    generate_offer: bool | None = None
    rtp: AudioBridgeRtpTransport | None = None


class AudioBridgeLeaveRequest(StrictBaseModel):
    request: Literal["leave"] = "leave"


class AudioBridgeChangeRoomRequest(StrictBaseModel):
    request: Literal["changeroom"] = "changeroom"
    room: RoomId = Field(ge=1)
    id: ParticipantId | None = Field(default=None, ge=1)
    pin: str | None = None
    group: str | None = None
    display: str | None = None
    token: str | None = None
    muted: bool | None = None
    suspended: bool | None = None
    pause_events: bool | None = None
    bitrate: int | None = Field(default=None, ge=0)
    quality: int | None = Field(default=None, ge=0, le=10)
    expected_loss: int | None = Field(default=None, ge=0, le=20)
    volume: int | None = Field(default=None, ge=0)
    spatial_position: int | None = Field(default=None, ge=0, le=100)
    denoise: bool | None = None


AudioBridgeRequest: TypeAlias = (
    AudioBridgeCreateRequest
    | AudioBridgeEditRequest
    | AudioBridgeDestroyRequest
    | AudioBridgeEnableRecordingRequest
    | AudioBridgeEnableMjrsRequest
    | AudioBridgeExistsRequest
    | AudioBridgeAllowedRequest
    | AudioBridgeKickRequest
    | AudioBridgeKickAllRequest
    | AudioBridgeSuspendRequest
    | AudioBridgeResumeRequest
    | AudioBridgeListRequest
    | AudioBridgeListParticipantsRequest
    | AudioBridgeResetDecoderRequest
    | AudioBridgeMuteRequest
    | AudioBridgeUnmuteRequest
    | AudioBridgeMuteRoomRequest
    | AudioBridgeUnmuteRoomRequest
    | AudioBridgeRtpForwardRequest
    | AudioBridgeStopRtpForwardRequest
    | AudioBridgeListForwardersRequest
    | AudioBridgePlayFileRequest
    | AudioBridgeIsPlayingRequest
    | AudioBridgeListAnnouncementsRequest
    | AudioBridgeStopFileRequest
    | AudioBridgeStopAllFilesRequest
    | AudioBridgeJoinRequest
    | AudioBridgeConfigureRequest
    | AudioBridgeLeaveRequest
    | AudioBridgeChangeRoomRequest
)


# Inbound data is intentionally permissive.  Known fields remain typed while
# unrecognized additions are retained in Pydantic's ``model_extra``.
class AudioBridgeRoom(LooseBaseModel):
    room: RoomId
    description: str | None = None
    pin_required: bool | None = None
    sampling_rate: int | None = None
    spatial_audio: bool | None = None
    record: bool | None = None
    num_participants: int | None = None


class AudioBridgeParticipant(LooseBaseModel):
    id: ParticipantId
    display: str | None = None
    setup: bool | None = None
    muted: bool | None = None
    suspended: bool | None = None
    talking: bool | None = None
    spatial_position: int | None = None
    group: str | None = None


class AudioBridgeRtpEndpoint(LooseBaseModel):
    ip: str | None = None
    port: int | None = None
    payload_type: int | None = None
    audiolevel_ext: int | None = None
    fec: bool | None = None


class AudioBridgeForwarder(LooseBaseModel):
    stream_id: StreamId
    group: str | None = None
    ip: str | None = None
    host: str | None = None
    port: int | None = None
    ssrc: int | None = None
    codec: str | None = None
    ptype: int | None = None
    srtp: bool | None = None
    always_on: bool | None = None


class AudioBridgeAnnouncement(LooseBaseModel):
    file_id: str
    filename: str
    playing: bool
    loop: bool | None = None


class AudioBridgeCreated(LooseBaseModel):
    audiobridge: Literal["created"]
    room: RoomId
    permanent: bool


class AudioBridgeEdited(LooseBaseModel):
    audiobridge: Literal["edited"]
    room: RoomId


class AudioBridgeDestroyed(LooseBaseModel):
    audiobridge: Literal["destroyed"]
    room: RoomId
    permanent: bool | None = None


class AudioBridgeSuccess(LooseBaseModel):
    audiobridge: Literal["success"]
    room: RoomId | None = None
    exists: bool | None = None
    allowed: list[str] | None = None
    group: str | None = None
    stream_id: StreamId | None = None
    host: str | None = None
    port: int | None = None
    file_id: str | None = None
    file_id_list: list[str] | None = None
    playing: bool | None = None
    permanent: bool | None = None


class AudioBridgeRooms(LooseBaseModel):
    audiobridge: Literal["success"]
    rooms: list[AudioBridgeRoom]


class AudioBridgeParticipants(LooseBaseModel):
    audiobridge: Literal["participants"]
    room: RoomId
    participants: list[AudioBridgeParticipant]


class AudioBridgeForwarders(LooseBaseModel):
    audiobridge: Literal["forwarders"]
    room: RoomId
    rtp_forwarders: list[AudioBridgeForwarder]


class AudioBridgeAnnouncements(LooseBaseModel):
    audiobridge: Literal["announcements"]
    room: RoomId
    announcements: list[AudioBridgeAnnouncement]


class AudioBridgeJoined(LooseBaseModel):
    audiobridge: Literal["joined"]
    room: RoomId
    id: ParticipantId | None = None
    display: str | None = None
    participants: list[AudioBridgeParticipant] | None = None
    rtp: AudioBridgeRtpEndpoint | None = None


class AudioBridgeRoomChanged(LooseBaseModel):
    audiobridge: Literal["roomchanged"]
    room: RoomId
    id: ParticipantId
    display: str | None = None
    participants: list[AudioBridgeParticipant] | None = None


class AudioBridgeEvent(LooseBaseModel):
    audiobridge: Literal["event"]
    room: RoomId | None = None
    result: str | None = None
    participants: list[AudioBridgeParticipant] | None = None
    leaving: ParticipantId | None = None
    muted: ParticipantId | None = None
    suspended: ParticipantId | None = None
    resumed: ParticipantId | None = None


class AudioBridgeLeft(LooseBaseModel):
    audiobridge: Literal["left"]
    room: RoomId
    id: ParticipantId


class AudioBridgeAnnouncementStarted(LooseBaseModel):
    audiobridge: Literal["announcement-started"]
    room: RoomId
    file_id: str


class AudioBridgeAnnouncementStopped(LooseBaseModel):
    audiobridge: Literal["announcement-stopped"]
    room: RoomId
    file_id: str


class UnknownAudioBridgeResponse(LooseBaseModel):
    """A future plugin response retained without weakening outbound models."""

    audiobridge: str | None = None


AudioBridgeResponse: TypeAlias = (
    AudioBridgeCreated
    | AudioBridgeEdited
    | AudioBridgeDestroyed
    | AudioBridgeSuccess
    | AudioBridgeRooms
    | AudioBridgeParticipants
    | AudioBridgeForwarders
    | AudioBridgeAnnouncements
    | AudioBridgeJoined
    | AudioBridgeRoomChanged
    | AudioBridgeEvent
    | AudioBridgeLeft
    | AudioBridgeAnnouncementStarted
    | AudioBridgeAnnouncementStopped
    | UnknownAudioBridgeResponse
)
ResponseT = TypeVar("ResponseT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class AudioBridgeReply(Generic[ResponseT]):
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
    raise AudioBridgeProtocolError(f"{context} must be a mapping or Pydantic model")


def parse_audiobridge_response(payload: Any) -> AudioBridgeReply[AudioBridgeResponse]:
    """Parse a core Janus envelope or a bare AudioBridge data object."""

    outer = _mapping(payload, context="response")
    transaction = outer.get("transaction")
    jsep_payload: Any = None

    if "janus" in outer:
        if outer.get("janus") == "error":
            error = _mapping(outer.get("error"), context="Janus error")
            raise AudioBridgeJanusError(
                int(error.get("code", -1)),
                str(error.get("reason", "unknown Janus error")),
                transaction=transaction,
            )
        plugin_data = _mapping(outer.get("plugindata"), context="plugindata")
        plugin = plugin_data.get("plugin")
        if plugin != "janus.plugin.audiobridge":
            raise AudioBridgeProtocolError(
                f"expected janus.plugin.audiobridge, received {plugin!r}"
            )
        data = _mapping(plugin_data.get("data"), context="plugin data")
        jsep_payload = outer.get("jsep")
    else:
        data = outer

    if "error_code" in data or "error" in data:
        raise AudioBridgePluginError(
            int(data.get("error_code", -1)),
            str(data.get("error", "unknown AudioBridge error")),
            transaction=transaction,
            raw=data,
        )

    kind = data.get("audiobridge")
    models: dict[str, type[BaseModel]] = {
        "created": AudioBridgeCreated,
        "edited": AudioBridgeEdited,
        "destroyed": AudioBridgeDestroyed,
        "participants": AudioBridgeParticipants,
        "forwarders": AudioBridgeForwarders,
        "announcements": AudioBridgeAnnouncements,
        "joined": AudioBridgeJoined,
        "roomchanged": AudioBridgeRoomChanged,
        "event": AudioBridgeEvent,
        "left": AudioBridgeLeft,
        "announcement-started": AudioBridgeAnnouncementStarted,
        "announcement-stopped": AudioBridgeAnnouncementStopped,
    }
    model: type[BaseModel]
    if kind == "success":
        model = AudioBridgeRooms if "rooms" in data else AudioBridgeSuccess
    else:
        model = models.get(str(kind), UnknownAudioBridgeResponse)

    try:
        parsed = model.model_validate(data)
        jsep = Jsep.model_validate(jsep_payload) if jsep_payload is not None else None
    except ValidationError as exc:
        raise AudioBridgeProtocolError("invalid AudioBridge response") from exc
    return AudioBridgeReply(
        data=parsed, jsep=jsep, transaction=transaction, raw=payload
    )
