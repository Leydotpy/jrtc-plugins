"""Forward-compatible response bodies for :mod:`janus.plugin.streaming`.

Janus wraps these bodies in its generic plugin-data envelope.  The named
response vocabulary belongs here, while ``jrtc`` remains responsible
only for parsing and transporting the outer Janus envelope.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import JanusId, SessionDescription
from .requests import MediaKind, MountpointType


class StreamingResponseModel(BaseModel):
    """Base that tolerates fields introduced by newer Janus releases."""

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class MediaSummary(StreamingResponseModel):
    mid: str
    label: str | None = None
    msid: str | None = None
    type: MediaKind
    age_ms: int | None = Field(default=None, ge=0)


class MediaInfo(MediaSummary):
    mindex: int | None = Field(default=None, ge=0)
    pt: int | None = Field(default=None, ge=0, le=127)
    codec: str | None = None
    rtpmap: str | None = None
    fmtp: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    rtp_port: int | None = Field(default=None, ge=1, le=65535)


class MountPointSummary(StreamingResponseModel):
    id: JanusId
    type: MountpointType
    description: str | None = None
    metadata: str | None = None
    enabled: bool | None = None
    media: list[MediaSummary] = Field(default_factory=list)


class MountPointInfo(StreamingResponseModel):
    id: JanusId
    name: str | None = None
    description: str | None = None
    metadata: str | None = None
    secret: str | None = Field(default=None, repr=False)
    pin: str | None = Field(default=None, repr=False)
    is_private: bool | None = None
    viewers: int | None = Field(default=None, ge=0)
    enabled: bool | None = None
    type: MountpointType
    media: list[MediaInfo] = Field(default_factory=list)


class CreatedPort(StreamingResponseModel):
    type: MediaKind
    mid: str
    msid: str | None = None
    port: int = Field(ge=1, le=65535)


class CreatedMountPoint(StreamingResponseModel):
    id: JanusId
    type: MountpointType
    description: str | None = None
    is_private: bool | None = None
    ports: list[CreatedPort] = Field(default_factory=list)


class ListResponse(StreamingResponseModel):
    streaming: Literal["list"] = "list"
    mountpoints: list[MountPointSummary] = Field(alias="list", default_factory=list)


class InfoResponse(StreamingResponseModel):
    streaming: Literal["info"] = "info"
    mountpoint: MountPointInfo = Field(alias="info")


class CreatedResponse(StreamingResponseModel):
    streaming: Literal["created"] = "created"
    create: str
    permanent: bool = False
    stream: CreatedMountPoint


class EditedResponse(StreamingResponseModel):
    streaming: Literal["edited"] = "edited"
    id: JanusId
    permanent: bool | None = None
    metadata: str | None = None


class DestroyedResponse(StreamingResponseModel):
    streaming: Literal["destroyed"] = "destroyed"
    id: JanusId


class OkResponse(StreamingResponseModel):
    streaming: Literal["ok"] = "ok"


class KickedAllResponse(StreamingResponseModel):
    streaming: Literal["kicked_all"] = "kicked_all"


class PreparingResponse(StreamingResponseModel):
    status: Literal["preparing"] = "preparing"
    jsep: SessionDescription | None = None


class StartingResponse(StreamingResponseModel):
    status: Literal["starting"] = "starting"
    jsep: SessionDescription | None = None


class PausingResponse(StreamingResponseModel):
    status: Literal["pausing"] = "pausing"


class StoppingResponse(StreamingResponseModel):
    status: Literal["stopping"] = "stopping"


class SwitchedResponse(StreamingResponseModel):
    switched: Literal["ok"] = "ok"
    id: JanusId


class StreamingErrorResponse(StreamingResponseModel):
    error_code: int | None = None
    error: str


type StreamingResponse = (
    ListResponse
    | InfoResponse
    | CreatedResponse
    | EditedResponse
    | DestroyedResponse
    | OkResponse
    | KickedAllResponse
    | PreparingResponse
    | StartingResponse
    | PausingResponse
    | StoppingResponse
    | SwitchedResponse
    | StreamingErrorResponse
)


__all__ = (
    "CreatedMountPoint",
    "CreatedPort",
    "CreatedResponse",
    "DestroyedResponse",
    "EditedResponse",
    "InfoResponse",
    "KickedAllResponse",
    "ListResponse",
    "MediaInfo",
    "MediaSummary",
    "MountPointInfo",
    "MountPointSummary",
    "OkResponse",
    "PausingResponse",
    "PreparingResponse",
    "StartingResponse",
    "StoppingResponse",
    "StreamingErrorResponse",
    "StreamingResponse",
    "StreamingResponseModel",
    "SwitchedResponse",
)
