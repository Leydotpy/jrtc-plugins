"""Record&Play request/response models and protocol parser."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar, Type

from jrtc.models.base import Jsep, PluginMessageBase
from jrtc.models.common import JanusId, LooseBaseModel
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .errors import RecordPlayJanusError, RecordPlayPluginError, RecordPlayProtocolError


class _RecordPlayRequest(PluginMessageBase):
    """Request base that normalizes user-entered names and paths, never SDP."""

    model_config = ConfigDict(str_strip_whitespace=True)


class ListRequest(_RecordPlayRequest):
    request: Literal["list"] = "list"
    admin_key: str | None = Field(default=None, min_length=1)


class UpdateRequest(_RecordPlayRequest):
    request: Literal["update"] = "update"
    admin_key: str | None = Field(default=None, min_length=1)


class ConfigureRequest(_RecordPlayRequest):
    request: Literal["configure"] = "configure"
    video_bitrate_max: int | None = Field(default=None, alias="video-bitrate-max", ge=0)
    video_keyframe_interval: int | None = Field(default=None, alias="video-keyframe-interval", ge=0)

    @model_validator(mode="after")
    def _has_setting(self) -> ConfigureRequest:
        if self.video_bitrate_max is None and self.video_keyframe_interval is None:
            raise ValueError("configure requires at least one setting")
        return self


class RecordRequest(_RecordPlayRequest):
    request: Literal["record"] = "record"
    id: JanusId | None = None
    name: str = Field(min_length=1)
    is_private: bool | None = None
    filename: str | None = Field(default=None, min_length=1)
    audiocodec: str | None = Field(default=None, min_length=1)
    videocodec: str | None = Field(default=None, min_length=1)
    videoprofile: str | None = Field(default=None, min_length=1)
    opusred: bool | None = None
    textdata: bool | None = None
    update: bool | None = None

    @model_validator(mode="after")
    def _validate_update(self) -> RecordRequest:
        if self.update is True and self.id is None:
            raise ValueError("updating a recording requires its id")
        return self


class PlayRequest(_RecordPlayRequest):
    request: Literal["play"] = "play"
    id: JanusId
    restart: bool | None = None


class StartRequest(_RecordPlayRequest):
    request: Literal["start"] = "start"


class PauseRequest(_RecordPlayRequest):
    request: Literal["pause"] = "pause"


class ResumeRequest(_RecordPlayRequest):
    request: Literal["resume"] = "resume"


class StopRequest(_RecordPlayRequest):
    request: Literal["stop"] = "stop"


class RecordingInfo(LooseBaseModel):
    """One entry in a Record&Play listing."""

    id: JanusId
    name: str
    date: str
    audio: bool | str | None = None
    video: bool | str | None = None
    data: bool | str | None = None
    audio_codec: str | None = None
    video_codec: str | None = None


class RecordingsList(LooseBaseModel):
    recordplay: Literal["list"]
    recordings: list[RecordingInfo] = Field(alias="list")


class RecordingsUpdated(LooseBaseModel):
    recordplay: Literal["ok"]


class ConfigureSettings(LooseBaseModel):
    video_bitrate_max: int | None = Field(default=None, alias="video-bitrate-max")
    video_keyframe_interval: int | None = Field(default=None, alias="video-keyframe-interval")


class Configured(LooseBaseModel):
    recordplay: Literal["configure"]
    status: Literal["ok"]
    settings: ConfigureSettings


RecordPlayStatus = Literal[
    "recording",
    "paused",
    "resumed",
    "stopped",
    "preparing",
    "playing",
    "done",
]


class RecordPlayResult(LooseBaseModel):
    status: RecordPlayStatus
    id: JanusId | None = None
    is_private: bool | None = None


class UnknownRecordPlayResult(LooseBaseModel):
    """A future Record&Play status retained for forward compatibility."""

    status: str | None = None


class RecordPlayEvent(LooseBaseModel):
    recordplay: Literal["event"]
    result: RecordPlayResult | UnknownRecordPlayResult


class UnknownRecordPlayResponse(LooseBaseModel):
    recordplay: str | None = None


RecordPlayResponse = (
    RecordingsList | RecordingsUpdated | Configured | RecordPlayEvent | UnknownRecordPlayResponse
)
ResponseT = TypeVar("ResponseT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class RecordPlayReply(Generic[ResponseT]):
    data: ResponseT
    jsep: Jsep | None = None
    transaction: str | None = None
    raw: Any = field(default=None, repr=False, compare=False)


def _mapping(value: Any, *, context: str) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", by_alias=True, exclude_none=False)
    if isinstance(value, Mapping):
        return dict(value)
    raise RecordPlayProtocolError(f"{context} must be a mapping or Pydantic model")


def _error_code(value: Any, *, context: str) -> int:
    if value is None:
        return -1
    if isinstance(value, bool):
        raise RecordPlayProtocolError(f"{context} error code must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RecordPlayProtocolError(f"{context} error code must be an integer") from exc


def parse_recordplay_response(payload: Any) -> RecordPlayReply[Type[RecordPlayResponse]]:
    """Parse an outer Janus response or bare Record&Play plugin data."""

    outer = _mapping(payload, context="response")
    transaction = outer.get("transaction")
    jsep_payload: Any = None
    if "janus" in outer:
        if outer.get("janus") == "error":
            error = _mapping(outer.get("error"), context="Janus error")
            raise RecordPlayJanusError(
                _error_code(error.get("code"), context="Janus"),
                str(error.get("reason", "unknown Janus error")),
                transaction=transaction,
            )
        plugin_data = _mapping(outer.get("plugindata"), context="plugindata")
        plugin = plugin_data.get("plugin")
        if plugin != "janus.plugin.recordplay":
            raise RecordPlayProtocolError(f"expected janus.plugin.recordplay, received {plugin!r}")
        data = _mapping(plugin_data.get("data"), context="plugin data")
        jsep_payload = outer.get("jsep")
    else:
        data = outer

    if "error_code" in data or "error" in data:
        raise RecordPlayPluginError(
            _error_code(data.get("error_code"), context="Record&Play"),
            str(data.get("error", "unknown Record&Play error")),
            transaction=transaction,
            raw=data,
        )

    models: dict[str, type[BaseModel]] = {
        "list": RecordingsList,
        "ok": RecordingsUpdated,
        "configure": Configured,
        "event": RecordPlayEvent,
    }
    try:
        kind = data.get("recordplay")
        model = (
            models.get(kind, UnknownRecordPlayResponse)
            if isinstance(kind, str)
            else UnknownRecordPlayResponse
        )
        parsed: RecordPlayResponse = model.model_validate(data)
        jsep = Jsep.model_validate(jsep_payload) if jsep_payload is not None else None
    except ValidationError as exc:
        raise RecordPlayProtocolError("invalid Record&Play response") from exc
    return RecordPlayReply(data=parsed, jsep=jsep, transaction=transaction, raw=payload)
