"""Strict requests and forward-compatible responses for VideoCall."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar

from jrtc.models.base import Jsep, PluginMessageBase
from jrtc.models.common import LooseBaseModel
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import VideoCallJanusError, VideoCallPluginError, VideoCallProtocolError


class _VideoCallRequest(PluginMessageBase):
    """Request base that normalizes human-entered strings, never SDP."""

    model_config = ConfigDict(str_strip_whitespace=True)


class ListRequest(_VideoCallRequest):
    request: Literal["list"] = "list"


class RegisterRequest(_VideoCallRequest):
    request: Literal["register"] = "register"
    username: str = Field(min_length=1)


class CallRequest(_VideoCallRequest):
    request: Literal["call"] = "call"
    username: str = Field(min_length=1)


class AcceptRequest(_VideoCallRequest):
    request: Literal["accept"] = "accept"


class SetRequest(_VideoCallRequest):
    request: Literal["set"] = "set"
    audio: bool | None = None
    video: bool | None = None
    bitrate: int | None = Field(default=None, ge=0)
    record: bool | None = None
    filename: str | None = Field(default=None, min_length=1)
    substream: int | None = Field(default=None, ge=0, le=2)
    temporal: int | None = Field(default=None, ge=0, le=2)
    fallback: int | None = Field(default=None, ge=0)


class HangupRequest(_VideoCallRequest):
    request: Literal["hangup"] = "hangup"


class PeerList(LooseBaseModel):
    peers: list[str] = Field(alias="list")


class Registered(LooseBaseModel):
    event: Literal["registered"]
    username: str


class Calling(LooseBaseModel):
    event: Literal["calling"]
    username: str


class IncomingCall(LooseBaseModel):
    event: Literal["incomingcall"]
    username: str


class Accepted(LooseBaseModel):
    event: Literal["accepted"]
    username: str


class SettingsApplied(LooseBaseModel):
    event: Literal["set"]


class Update(LooseBaseModel):
    event: Literal["update"]


class HungUp(LooseBaseModel):
    event: Literal["hangup"]
    username: str | None = None
    reason: str | None = None


class UnknownVideoCallResult(LooseBaseModel):
    event: str | None = None


VideoCallResult = (
    PeerList
    | Registered
    | Calling
    | IncomingCall
    | Accepted
    | SettingsApplied
    | Update
    | HungUp
    | UnknownVideoCallResult
)


class VideoCallEvent(LooseBaseModel):
    videocall: Literal["event"]
    result: VideoCallResult


class UnknownVideoCallResponse(LooseBaseModel):
    videocall: str | None = None
    result: Any = None


VideoCallResponse = VideoCallEvent | UnknownVideoCallResponse
ResponseT = TypeVar("ResponseT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class VideoCallReply(Generic[ResponseT]):
    data: ResponseT
    jsep: Jsep | None = None
    transaction: str | None = None
    raw: Any = field(default=None, repr=False, compare=False)


def _mapping(value: Any, *, context: str) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", by_alias=True, exclude_none=False)
    if isinstance(value, Mapping):
        return dict(value)
    raise VideoCallProtocolError(f"{context} must be a mapping or Pydantic model")


def _error_code(value: Any, *, context: str) -> int:
    if value is None:
        return -1
    if isinstance(value, bool):
        raise VideoCallProtocolError(f"{context} error code must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise VideoCallProtocolError(f"{context} error code must be an integer") from exc


def _result_model(result: dict[str, Any]) -> BaseModel:
    if "list" in result:
        return PeerList.model_validate(result)
    models: dict[str, type[BaseModel]] = {
        "registered": Registered,
        "calling": Calling,
        "incomingcall": IncomingCall,
        "accepted": Accepted,
        "set": SettingsApplied,
        "update": Update,
        "hangup": HungUp,
    }
    event = result.get("event")
    model = (
        models.get(event, UnknownVideoCallResult)
        if isinstance(event, str)
        else UnknownVideoCallResult
    )
    return model.model_validate(result)


def parse_videocall_response(payload: Any) -> VideoCallReply[VideoCallResponse]:
    """Parse an outer Janus event or a bare VideoCall plugin response."""

    outer = _mapping(payload, context="response")
    transaction = outer.get("transaction")
    jsep_payload: Any = None
    if "janus" in outer:
        if outer.get("janus") == "error":
            error = _mapping(outer.get("error"), context="Janus error")
            raise VideoCallJanusError(
                _error_code(error.get("code"), context="Janus"),
                str(error.get("reason", "unknown Janus error")),
                transaction=transaction,
            )
        plugin_data = _mapping(outer.get("plugindata"), context="plugindata")
        plugin = plugin_data.get("plugin")
        if plugin != "janus.plugin.videocall":
            raise VideoCallProtocolError(f"expected janus.plugin.videocall, received {plugin!r}")
        data = _mapping(plugin_data.get("data"), context="plugin data")
        jsep_payload = outer.get("jsep")
    else:
        data = outer

    if "error_code" in data or "error" in data:
        raise VideoCallPluginError(
            _error_code(data.get("error_code"), context="VideoCall"),
            str(data.get("error", "unknown VideoCall error")),
            transaction=transaction,
            raw=data,
        )

    try:
        if data.get("videocall") == "event" and isinstance(data.get("result"), Mapping):
            result = _result_model(dict(data["result"]))
            parsed: VideoCallResponse = VideoCallEvent.model_validate({**data, "result": result})
        else:
            parsed = UnknownVideoCallResponse.model_validate(data)
        jsep = Jsep.model_validate(jsep_payload) if jsep_payload is not None else None
    except ValidationError as exc:
        raise VideoCallProtocolError("invalid VideoCall response") from exc
    return VideoCallReply(data=parsed, jsep=jsep, transaction=transaction, raw=payload)
