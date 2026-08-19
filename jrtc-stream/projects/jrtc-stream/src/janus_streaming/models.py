from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def validate_janus_id(value: object, *, name: str = "id") -> int:
    """Validate a numeric Janus identifier without coercing strings or booleans."""

    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


type JanusId = Annotated[
    int,
    BeforeValidator(validate_janus_id),
    Field(strict=True, gt=0),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class SessionDescription(StrictModel):
    type: Literal["offer", "answer"]
    sdp: str = Field(min_length=1, repr=False)


class IceCandidate(StrictModel):
    candidate: str = Field(min_length=1, repr=False)
    sdp_mid: str | None = Field(default=None, alias="sdpMid")
    sdp_mline_index: int | None = Field(default=None, alias="sdpMLineIndex", ge=0)


class ViewerState(StrEnum):
    NEW = "new"
    OFFERED = "offered"
    ACTIVE = "active"
    PAUSED = "paused"
    FAILED = "failed"
    CLOSED = "closed"


class AudioTrackSpec(StrictModel):
    type: Literal["audio"] = "audio"
    mid: str = Field(min_length=1, max_length=64)
    port: int | None = Field(default=None, ge=1, le=65535)
    rtcp_port: int | None = Field(default=None, ge=1, le=65535)
    payload_type: int = Field(default=111, ge=0, le=127)
    codec: str = Field(default="opus", min_length=1)
    fmtp: str | None = None
    multicast: str | None = None
    bind_interface: str | None = None
    skew: bool = False
    label: str | None = None
    msid: str | None = None


class VideoTrackSpec(StrictModel):
    type: Literal["video"] = "video"
    mid: str = Field(min_length=1, max_length=64)
    port: int | None = Field(default=None, ge=1, le=65535)
    rtcp_port: int | None = Field(default=None, ge=1, le=65535)
    payload_type: int = Field(default=96, ge=0, le=127)
    codec: str = Field(default="h264", min_length=1)
    fmtp: str | None = None
    multicast: str | None = None
    bind_interface: str | None = None
    skew: bool = False
    simulcast: bool = False
    port2: int | None = Field(default=None, ge=1, le=65535)
    port3: int | None = Field(default=None, ge=1, le=65535)
    svc: bool = False
    h264_sps: str | None = None
    collision_ms: int | None = Field(default=None, ge=0)
    label: str | None = None
    msid: str | None = None


class DataTrackSpec(StrictModel):
    type: Literal["data"] = "data"
    mid: str = Field(min_length=1, max_length=64)
    port: int | None = Field(default=None, ge=1, le=65535)
    data_type: Literal["text", "binary"] = "text"
    buffer_latest_message: bool = False
    multicast: str | None = None
    bind_interface: str | None = None
    label: str | None = None
    msid: str | None = None


TrackSpec = Annotated[AudioTrackSpec | VideoTrackSpec | DataTrackSpec, Field(discriminator="type")]


class RtpMountpointSpec(StrictModel):
    id: JanusId | None = None
    name: str | None = None
    description: str | None = None
    metadata: str | None = None
    private: bool = True
    secret: str | None = Field(default=None, repr=False)
    pin: str | None = Field(default=None, repr=False)
    enabled: bool = False
    permanent: bool = False
    media: tuple[TrackSpec, ...] = Field(min_length=1)
    threads: int | None = Field(default=None, ge=0)
    buffer_keyframes_ms: int | None = Field(default=None, ge=0)
    buffer_keyframes_bytes: int | None = Field(default=None, ge=0)
    srtp_suite: Literal[32, 80] | None = None
    srtp_crypto: str | None = Field(default=None, repr=False)
    e2ee: bool | None = None

    @model_validator(mode="after")
    def unique_mids(self) -> RtpMountpointSpec:
        mids = [item.mid for item in self.media]
        if len(mids) != len(set(mids)):
            raise ValueError("media mids must be unique")
        return self


class RtspMountpointSpec(StrictModel):
    id: JanusId | None = None
    url: str = Field(min_length=1)
    name: str | None = None
    description: str | None = None
    metadata: str | None = None
    private: bool = True
    secret: str | None = Field(default=None, repr=False)
    pin: str | None = Field(default=None, repr=False)
    enabled: bool = False
    permanent: bool = False
    username: str | None = None
    password: str | None = Field(default=None, repr=False)
    reconnect_delay_seconds: int | None = Field(default=5, ge=0)
    session_timeout_seconds: int | None = Field(default=None, ge=0)
    media_timeout_seconds: int | None = Field(default=None, ge=0)
    connection_timeout_seconds: int | None = Field(default=None, ge=0)
    bind_interface: str | None = None
    notify_changes: bool = True
    fail_check: bool | None = None
    quirk: bool | None = None


class FileMountpointSpec(StrictModel):
    type: Literal["live", "ondemand"]
    id: JanusId | None = None
    filename: str = Field(min_length=1)
    name: str | None = None
    description: str | None = None
    metadata: str | None = None
    private: bool = True
    secret: str | None = Field(default=None, repr=False)
    pin: str | None = Field(default=None, repr=False)
    enabled: bool = False
    permanent: bool = False
    audio: bool = True
    video: bool = False


class MountpointTrack(StrictModel):
    mid: str
    type: Literal["audio", "video", "data"]
    label: str | None = None
    msid: str | None = None
    mindex: int | None = None
    age_ms: int | None = Field(default=None, ge=0)
    payload_type: int | None = Field(default=None, ge=0, le=127)
    codec: str | None = None
    rtpmap: str | None = None
    fmtp: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)


class MountpointSummary(StrictModel):
    id: JanusId
    type: Literal["rtp", "live", "ondemand", "rtsp"]
    description: str | None = None
    metadata: str | None = None
    enabled: bool | None = None
    media: tuple[MountpointTrack, ...] = ()


class MountpointInfo(StrictModel):
    id: JanusId
    type: Literal["rtp", "live", "ondemand", "rtsp"]
    name: str | None = None
    description: str | None = None
    metadata: str | None = None
    private: bool | None = None
    viewers: int = Field(default=0, ge=0)
    enabled: bool | None = None
    media: tuple[MountpointTrack, ...] = ()


class CreatedPort(StrictModel):
    type: Literal["audio", "video", "data"]
    mid: str
    port: int = Field(ge=1, le=65535)
    msid: str | None = None


class CreatedMountpoint(StrictModel):
    id: JanusId
    type: Literal["rtp", "live", "ondemand", "rtsp"]
    description: str | None = None
    private: bool | None = None
    permanent: bool = False
    ports: tuple[CreatedPort, ...] = ()


class ConfigureStream(StrictModel):
    mid: str
    send: bool | None = None
    substream: int | None = Field(default=None, ge=0, le=2)
    temporal: int | None = Field(default=None, ge=0, le=2)
    fallback_microseconds: int | None = Field(default=250_000, ge=0)
    spatial_layer: int | None = Field(default=None, ge=0, le=1)
    temporal_layer: int | None = Field(default=None, ge=0, le=2)
    min_delay: int | None = Field(default=None, ge=0)
    max_delay: int | None = Field(default=None, ge=0)
