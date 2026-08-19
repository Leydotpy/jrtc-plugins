"""Validated request bodies for :mod:`janus.plugin.streaming`.

These models intentionally live in the Streaming distribution rather than in
``jrtc``.  Core transports plugin bodies as opaque mappings; this
module owns the Streaming protocol vocabulary and its field-level validation.

The wire field names follow the current Janus multistream API.  Deprecated
single-track create/configure fields are retained for compatibility, while new
code should prefer ``media`` and ``streams``.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import JanusId

type MediaKind = Literal["audio", "video", "data"]
type MountpointType = Literal["rtp", "live", "ondemand", "rtsp"]


class Track(TypedDict, total=False):
    """Wire-level track options accepted by dynamic mountpoint creation."""

    type: MediaKind
    mid: str
    msid: str | None
    label: str | None
    mcast: str | None
    iface: str | None
    port: int | None
    rtcpport: int | None
    pt: int | None
    codec: str | None
    fmtp: str | None
    skew: bool
    simulcast: bool
    port2: int | None
    port3: int | None
    svc: bool
    h264sps: str | None
    collision: int | None
    datatype: Literal["text", "binary"]
    databuffermsg: bool


class AudioTrack(TypedDict, total=False):
    type: Literal["audio"]
    mid: str
    msid: str | None
    label: str | None
    mcast: str | None
    iface: str | None
    port: int | None
    rtcpport: int | None
    pt: int | None
    codec: str | None
    fmtp: str | None
    skew: bool


class VideoTrack(TypedDict, total=False):
    type: Literal["video"]
    mid: str
    msid: str | None
    label: str | None
    mcast: str | None
    iface: str | None
    port: int | None
    rtcpport: int | None
    pt: int | None
    codec: str | None
    fmtp: str | None
    skew: bool
    simulcast: bool
    port2: int | None
    port3: int | None
    svc: bool
    h264sps: str | None
    collision: int | None


class DataTrack(TypedDict, total=False):
    type: Literal["data"]
    mid: str
    msid: str | None
    label: str | None
    mcast: str | None
    iface: str | None
    port: int | None
    datatype: Literal["text", "binary"]
    databuffermsg: bool


type MediaStream = AudioTrack | VideoTrack | DataTrack


class MountPoint(TypedDict, total=False):
    """Keyword options accepted by :meth:`StreamingPlugin.create`.

    Runtime validation is performed by :class:`CreateRequest`; this TypedDict
    exists to keep the convenience helper discoverable without depending on a
    core-owned named-plugin type.
    """

    type: MountpointType
    id: JanusId
    name: str | None
    description: str | None
    metadata: str | None
    secret: str | None
    pin: str | None
    is_private: bool
    permanent: bool
    enabled: bool
    media: list[MediaStream | CreateMedia]
    filename: str | None
    audio: bool | None
    video: bool | None
    data: bool | None
    audioport: int | None
    audiortcpport: int | None
    audiomcast: str | None
    audioiface: str | None
    audiopt: int | None
    audiocodec: str | None
    audiofmtp: str | None
    audioskew: bool | None
    videoport: int | None
    videortcpport: int | None
    videomcast: str | None
    videoiface: str | None
    videopt: int | None
    videocodec: str | None
    videofmtp: str | None
    videosimulcast: bool | None
    videoport2: int | None
    videoport3: int | None
    videoskew: bool | None
    videosvc: bool | None
    h264sps: str | None
    collision: int | None
    dataport: int | None
    datamcast: str | None
    dataiface: str | None
    datatype: Literal["text", "binary"] | None
    databuffermsg: bool | None
    threads: int | None
    bufferkf_ms: int | None
    bufferkf_bytes: int | None
    srtpsuite: Literal[32, 80] | None
    srtpcrypto: str | None
    e2ee: bool | None
    playoutdelay_ext: bool | None
    abscapturetime_src_ext_id: int | None
    url: str | None
    rtsp_user: str | None
    rtsp_pwd: str | None
    rtsp_quirk: bool | None
    rtsp_failcheck: bool | None
    rtspiface: str | None
    rtsp_reconnect_delay: int | None
    rtsp_session_timeout: int | None
    rtsp_timeout: int | None
    rtsp_conn_timeout: int | None
    rtsp_notify_changes: bool | None


class StreamingRequestModel(BaseModel):
    """Strict, immutable base for outbound Streaming request bodies."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class CreateMediaBase(StreamingRequestModel):
    """Fields shared by tracks in a multistream RTP mountpoint."""

    type: MediaKind
    mid: str = Field(min_length=1, max_length=64)
    msid: str | None = None
    label: str | None = None


class CreateAudioMedia(CreateMediaBase):
    type: Literal["audio"] = "audio"
    mcast: str | None = None
    iface: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    rtcpport: int | None = Field(default=None, ge=1, le=65535)
    pt: int | None = Field(default=None, ge=0, le=127)
    codec: str | None = None
    fmtp: str | None = None
    skew: bool = False


class CreateVideoMedia(CreateMediaBase):
    type: Literal["video"] = "video"
    mcast: str | None = None
    iface: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    rtcpport: int | None = Field(default=None, ge=1, le=65535)
    pt: int | None = Field(default=None, ge=0, le=127)
    codec: str | None = None
    fmtp: str | None = None
    skew: bool = False
    simulcast: bool = False
    port2: int | None = Field(default=None, ge=1, le=65535)
    port3: int | None = Field(default=None, ge=1, le=65535)
    svc: bool = False
    h264sps: str | None = None
    collision: int | None = Field(default=None, ge=0)


class CreateDataMedia(CreateMediaBase):
    type: Literal["data"] = "data"
    mcast: str | None = None
    iface: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    datatype: Literal["text", "binary"] = "text"
    databuffermsg: bool = False


type CreateMedia = Annotated[
    CreateAudioMedia | CreateVideoMedia | CreateDataMedia,
    Field(discriminator="type"),
]


class RecordingMedia(StreamingRequestModel):
    """Per-track recording selection for the modern recording API."""

    mid: str = Field(min_length=1, max_length=64)
    filename: str | None = None


class ConfigureStream(StreamingRequestModel):
    """One media-line update in a ``configure`` request."""

    mid: str = Field(min_length=1, max_length=64)
    send: bool | None = None
    substream: int | None = Field(default=None, ge=0, le=2)
    temporal: int | None = Field(default=None, ge=0, le=2)
    fallback: int | None = Field(default=250_000, ge=0, description="Microseconds")
    spatial_layer: int | None = Field(default=None, ge=0, le=1)
    temporal_layer: int | None = Field(default=None, ge=0, le=2)
    min_delay: int | None = Field(default=None, ge=0)
    max_delay: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_delay_range(self) -> ConfigureStream:
        if (
            self.min_delay is not None
            and self.max_delay is not None
            and self.min_delay > self.max_delay
        ):
            raise ValueError("min_delay must not exceed max_delay")
        return self


class ListRequest(StreamingRequestModel):
    request: Literal["list"] = "list"


class InfoRequest(StreamingRequestModel):
    request: Literal["info"] = "info"
    id: JanusId
    secret: str | None = Field(default=None, repr=False)


class CreateRequest(StreamingRequestModel):
    """Create an RTP, RTSP, live-file, or on-demand mountpoint."""

    request: Literal["create"] = "create"
    admin_key: str | None = Field(default=None, repr=False)
    type: MountpointType
    id: JanusId | None = None
    name: str | None = None
    description: str | None = None
    metadata: str | None = None
    secret: str | None = Field(default=None, repr=False)
    pin: str | None = Field(default=None, repr=False)
    is_private: bool = True
    permanent: bool = False
    enabled: bool = False
    media: list[CreateMedia] = Field(default_factory=list)

    # File mountpoints.
    filename: str | None = None
    audio: bool | None = None
    video: bool | None = None
    data: bool | None = None

    # Legacy single-track RTP syntax.
    audioport: int | None = Field(default=None, ge=1, le=65535)
    audiortcpport: int | None = Field(default=None, ge=1, le=65535)
    audiomcast: str | None = None
    audioiface: str | None = None
    audiopt: int | None = Field(default=None, ge=0, le=127)
    audiocodec: str | None = None
    audiofmtp: str | None = None
    audioskew: bool | None = None
    videoport: int | None = Field(default=None, ge=1, le=65535)
    videortcpport: int | None = Field(default=None, ge=1, le=65535)
    videomcast: str | None = None
    videoiface: str | None = None
    videopt: int | None = Field(default=None, ge=0, le=127)
    videocodec: str | None = None
    videofmtp: str | None = None
    videosimulcast: bool | None = None
    videoport2: int | None = Field(default=None, ge=1, le=65535)
    videoport3: int | None = Field(default=None, ge=1, le=65535)
    videoskew: bool | None = None
    videosvc: bool | None = None
    h264sps: str | None = None
    collision: int | None = Field(default=None, ge=0)
    dataport: int | None = Field(default=None, ge=1, le=65535)
    datamcast: str | None = None
    dataiface: str | None = None
    datatype: Literal["text", "binary"] | None = None
    databuffermsg: bool | None = None

    threads: int | None = Field(default=None, ge=0)
    bufferkf_ms: int | None = Field(default=None, ge=0)
    bufferkf_bytes: int | None = Field(default=None, ge=0)
    srtpsuite: Literal[32, 80] | None = None
    srtpcrypto: str | None = Field(default=None, repr=False)
    e2ee: bool | None = None
    playoutdelay_ext: bool | None = None
    abscapturetime_src_ext_id: int | None = Field(default=None, ge=1, le=14)

    # RTSP mountpoints.
    url: str | None = None
    rtsp_user: str | None = None
    rtsp_pwd: str | None = Field(default=None, repr=False)
    rtsp_quirk: bool | None = None
    rtsp_failcheck: bool | None = None
    rtspiface: str | None = None
    rtsp_reconnect_delay: int | None = Field(default=None, ge=0)
    rtsp_session_timeout: int | None = Field(default=None, ge=0)
    rtsp_timeout: int | None = Field(default=None, ge=0)
    rtsp_conn_timeout: int | None = Field(default=None, ge=0)
    rtsp_notify_changes: bool | None = None

    @model_validator(mode="after")
    def validate_srtp_pair(self) -> CreateRequest:
        if (self.srtpsuite is None) != (self.srtpcrypto is None):
            raise ValueError("srtpsuite and srtpcrypto must be provided together")
        return self


class DestroyRequest(StreamingRequestModel):
    request: Literal["destroy"] = "destroy"
    id: JanusId
    secret: str | None = Field(default=None, repr=False)
    permanent: bool = False


class EditRequest(StreamingRequestModel):
    request: Literal["edit"] = "edit"
    id: JanusId
    secret: str | None = Field(default=None, repr=False)
    new_description: str | None = None
    new_metadata: str | None = None
    new_secret: str | None = Field(default=None, repr=False)
    new_pin: str | None = Field(default=None, repr=False)
    new_is_private: bool | None = None
    permanent: bool = False
    edited_event: bool = False


class EnableRequest(StreamingRequestModel):
    request: Literal["enable"] = "enable"
    id: JanusId
    secret: str | None = Field(default=None, repr=False)


class DisableRequest(StreamingRequestModel):
    request: Literal["disable"] = "disable"
    id: JanusId
    stop_recording: bool = True
    secret: str | None = Field(default=None, repr=False)


class KickAllRequest(StreamingRequestModel):
    request: Literal["kick_all"] = "kick_all"
    id: JanusId
    secret: str | None = Field(default=None, repr=False)


class RecordingRequest(StreamingRequestModel):
    request: Literal["recording"] = "recording"
    action: Literal["start", "stop"]
    id: JanusId
    media: list[RecordingMedia] = Field(default_factory=list)


class WatchRequest(StreamingRequestModel):
    request: Literal["watch"] = "watch"
    id: JanusId
    pin: str | None = Field(default=None, repr=False)
    media: list[str] = Field(default_factory=list)
    offer_audio: bool | None = None
    offer_video: bool | None = None
    offer_data: bool | None = None


class StartRequest(StreamingRequestModel):
    request: Literal["start"] = "start"


class PauseRequest(StreamingRequestModel):
    request: Literal["pause"] = "pause"


class ConfigureRequest(StreamingRequestModel):
    request: Literal["configure"] = "configure"
    streams: list[ConfigureStream] = Field(default_factory=list)
    audio: bool | None = None
    video: bool | None = None
    data: bool | None = None


class SwitchRequest(StreamingRequestModel):
    request: Literal["switch"] = "switch"
    id: JanusId


class StopRequest(StreamingRequestModel):
    request: Literal["stop"] = "stop"


type StreamingRequest = (
    ListRequest
    | InfoRequest
    | CreateRequest
    | DestroyRequest
    | EditRequest
    | EnableRequest
    | DisableRequest
    | KickAllRequest
    | RecordingRequest
    | WatchRequest
    | StartRequest
    | PauseRequest
    | ConfigureRequest
    | SwitchRequest
    | StopRequest
)


__all__ = (
    "AudioTrack",
    "ConfigureRequest",
    "ConfigureStream",
    "CreateAudioMedia",
    "CreateDataMedia",
    "CreateMedia",
    "CreateMediaBase",
    "CreateRequest",
    "CreateVideoMedia",
    "DataTrack",
    "DestroyRequest",
    "DisableRequest",
    "EditRequest",
    "EnableRequest",
    "InfoRequest",
    "KickAllRequest",
    "ListRequest",
    "MediaKind",
    "MediaStream",
    "MountPoint",
    "MountpointType",
    "PauseRequest",
    "RecordingMedia",
    "RecordingRequest",
    "StartRequest",
    "StopRequest",
    "StreamingRequest",
    "StreamingRequestModel",
    "SwitchRequest",
    "Track",
    "VideoTrack",
    "WatchRequest",
)
