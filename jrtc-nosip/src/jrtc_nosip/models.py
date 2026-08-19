"""NoSIP request/response wire schemas and parser."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeAlias, TypeVar

from jrtc.models.base import Jsep, PluginMessageBase
from jrtc.models.common import JanusId, LooseBaseModel, StrictBaseModel
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from .errors import NoSipJanusError, NoSipPluginError, NoSipProtocolError

SrtpPolicy: TypeAlias = Literal["sdes_mandatory", "sdes_optional"]
StreamType: TypeAlias = Literal["audio", "video", "peer_audio", "peer_video"]


class _NoSipRequest(PluginMessageBase):
    """Request base that trims ordinary text fields."""

    model_config = ConfigDict(str_strip_whitespace=True)


class GenerateRequest(_NoSipRequest):
    request: Literal["generate"] = "generate"
    info: str | None = Field(default=None, min_length=1)
    srtp: SrtpPolicy | None = None
    srtp_profile: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _profile_requires_srtp(self) -> GenerateRequest:
        if self.srtp_profile is not None and self.srtp is None:
            raise ValueError("srtp_profile requires an srtp policy")
        return self


class ProcessRequest(_NoSipRequest):
    # SDP is line-oriented protocol text: stripping it would alter the wire
    # payload (and can remove the required trailing CRLF).
    model_config = ConfigDict(str_strip_whitespace=False)

    request: Literal["process"] = "process"
    type: Literal["offer", "answer"]
    sdp: str = Field(min_length=1)
    info: str | None = Field(default=None, min_length=1)
    srtp: SrtpPolicy | None = None
    srtp_profile: str | None = Field(default=None, min_length=1)

    @field_validator("info", "srtp_profile")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @model_validator(mode="after")
    def _validate_sdp_and_srtp(self) -> ProcessRequest:
        if not self.sdp.strip():
            raise ValueError("sdp must not be blank")
        if self.srtp_profile is not None and self.srtp is None:
            raise ValueError("srtp_profile requires an srtp policy")
        return self


class HangupRequest(_NoSipRequest):
    request: Literal["hangup"] = "hangup"


class RecordingRequest(_NoSipRequest):
    request: Literal["recording"] = "recording"
    action: Literal["start", "stop"]
    audio: bool | None = None
    video: bool | None = None
    peer_audio: bool | None = None
    peer_video: bool | None = None
    filename: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _has_direction(self) -> RecordingRequest:
        directions = (self.audio, self.video, self.peer_audio, self.peer_video)
        if not any(value is True for value in directions):
            raise ValueError("select at least one recording direction")
        return self


class KeyframeRequest(_NoSipRequest):
    request: Literal["keyframe"] = "keyframe"
    user: bool | None = None
    peer: bool | None = None

    @model_validator(mode="after")
    def _has_target(self) -> KeyframeRequest:
        if self.user is not True and self.peer is not True:
            raise ValueError("select user, peer, or both")
        return self


class ForwardStream(StrictBaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    type: StreamType
    host: str = Field(min_length=1)
    host_family: Literal["ipv4", "ipv6"] | None = None
    port: int = Field(ge=1, le=65535)
    ssrc: int | None = Field(default=None, ge=0, le=4_294_967_295)
    pt: int | None = Field(default=None, ge=0, le=127)
    srtp_suite: Literal[32, 80] | None = None
    srtp_crypto: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _complete_srtp_pair(self) -> ForwardStream:
        if (self.srtp_suite is None) != (self.srtp_crypto is None):
            raise ValueError("srtp_suite and srtp_crypto must be supplied together")
        return self


class RtpForwardRequest(_NoSipRequest):
    request: Literal["rtp_forward"] = "rtp_forward"
    streams: list[ForwardStream] = Field(min_length=1)


class StopRtpForwardRequest(_NoSipRequest):
    request: Literal["stop_rtp_forward"] = "stop_rtp_forward"
    stream_id: JanusId


class ListForwardersRequest(_NoSipRequest):
    request: Literal["listforwarders"] = "listforwarders"


class Generated(LooseBaseModel):
    event: Literal["generated"]
    type: Literal["offer", "answer"]
    sdp: str
    unique_id: str | None = None


class Processed(LooseBaseModel):
    event: Literal["processed"]
    type: Literal["offer", "answer"] | None = None
    srtp: SrtpPolicy | None = None
    unique_id: str | None = None


class HangingUp(LooseBaseModel):
    event: Literal["hangingup"]


class RecordingUpdated(LooseBaseModel):
    event: Literal["recordingupdated"]


class KeyframeSent(LooseBaseModel):
    event: Literal["keyframesent"]


class Forwarder(LooseBaseModel):
    stream_id: JanusId
    type: StreamType
    host: str
    port: int
    media: Literal["audio", "video"] | None = None
    ssrc: int | None = None
    pt: int | None = None
    srtp: bool | None = None


class RtpForwarded(LooseBaseModel):
    event: Literal["rtp_forward"]
    forwarders: list[Forwarder] = Field(default_factory=list)


class RtpForwardStopped(LooseBaseModel):
    event: Literal["stop_rtp_forward"]
    stream_id: JanusId


class ForwardersListed(LooseBaseModel):
    event: Literal["forwarders"]
    forwarders: list[Forwarder] = Field(default_factory=list)


class UnknownNoSipResult(LooseBaseModel):
    event: str | None = None


NoSipResult = (
    Generated
    | Processed
    | HangingUp
    | RecordingUpdated
    | KeyframeSent
    | RtpForwarded
    | RtpForwardStopped
    | ForwardersListed
    | UnknownNoSipResult
)


class NoSipEvent(LooseBaseModel):
    nosip: Literal["event"]
    result: NoSipResult


class UnknownNoSipResponse(LooseBaseModel):
    nosip: str | None = None
    result: Any = None


NoSipResponse = NoSipEvent | UnknownNoSipResponse
ResponseT = TypeVar("ResponseT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class NoSipReply(Generic[ResponseT]):
    data: ResponseT
    jsep: Jsep | None = None
    transaction: str | None = None
    raw: Any = field(default=None, repr=False, compare=False)


def _mapping(value: Any, *, context: str) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", by_alias=True, exclude_none=False)
    if isinstance(value, Mapping):
        return dict(value)
    raise NoSipProtocolError(f"{context} must be a mapping or Pydantic model")


def _error_code(value: Any, *, context: str) -> int:
    if value is None:
        return -1
    if isinstance(value, bool):
        raise NoSipProtocolError(f"{context} error code must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise NoSipProtocolError(f"{context} error code must be an integer") from exc


def _result_model(result: dict[str, Any]) -> BaseModel:
    models: dict[str, type[BaseModel]] = {
        "generated": Generated,
        "processed": Processed,
        "hangingup": HangingUp,
        "recordingupdated": RecordingUpdated,
        "keyframesent": KeyframeSent,
        "rtp_forward": RtpForwarded,
        "stop_rtp_forward": RtpForwardStopped,
        "forwarders": ForwardersListed,
    }
    event = result.get("event")
    model = models.get(event, UnknownNoSipResult) if isinstance(event, str) else UnknownNoSipResult
    return model.model_validate(result)


def parse_nosip_response(payload: Any) -> NoSipReply[NoSipResponse]:
    """Parse a Janus envelope or bare NoSIP response into typed data."""

    outer = _mapping(payload, context="response")
    transaction = outer.get("transaction")
    jsep_payload: Any = None
    if "janus" in outer:
        if outer.get("janus") == "error":
            error = _mapping(outer.get("error"), context="Janus error")
            raise NoSipJanusError(
                _error_code(error.get("code"), context="Janus"),
                str(error.get("reason", "unknown Janus error")),
                transaction=transaction,
            )
        plugin_data = _mapping(outer.get("plugindata"), context="plugindata")
        plugin = plugin_data.get("plugin")
        if plugin != "janus.plugin.nosip":
            raise NoSipProtocolError(f"expected janus.plugin.nosip, received {plugin!r}")
        data = _mapping(plugin_data.get("data"), context="plugin data")
        jsep_payload = outer.get("jsep")
    else:
        data = outer

    if "error_code" in data or "error" in data:
        raise NoSipPluginError(
            _error_code(data.get("error_code"), context="NoSIP"),
            str(data.get("error", "unknown NoSIP error")),
            transaction=transaction,
            raw=data,
        )

    try:
        if data.get("nosip") == "event" and isinstance(data.get("result"), Mapping):
            result = _result_model(dict(data["result"]))
            parsed: NoSipResponse = NoSipEvent.model_validate({**data, "result": result})
        else:
            parsed = UnknownNoSipResponse.model_validate(data)
        jsep = Jsep.model_validate(jsep_payload) if jsep_payload is not None else None
    except ValidationError as exc:
        raise NoSipProtocolError("invalid NoSIP response") from exc
    return NoSipReply(data=parsed, jsep=jsep, transaction=transaction, raw=payload)
