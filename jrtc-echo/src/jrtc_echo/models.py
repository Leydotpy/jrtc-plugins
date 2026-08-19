"""Wire models and response parser for the Janus EchoTest plugin."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar

from jrtc.models.base import Jsep
from jrtc.models.common import LooseBaseModel, StrictBaseModel
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import EchoTestJanusError, EchoTestPluginError, EchoTestProtocolError


class EchoTestRequest(StrictBaseModel):
    """The plugin's single unnamed request; every documented field is optional."""

    model_config = ConfigDict(str_strip_whitespace=True)

    audio: bool | None = None
    audiocodec: str | None = Field(default=None, min_length=1)
    video: bool | None = None
    videocodec: str | None = Field(default=None, min_length=1)
    videoprofile: str | None = Field(default=None, min_length=1)
    bitrate: int | None = Field(default=None, ge=0)
    record: bool | None = None
    filename: str | None = Field(default=None, min_length=1)
    substream: int | None = Field(default=None, ge=0, le=2)
    temporal: int | None = Field(default=None, ge=0, le=2)
    svc: bool | None = None
    spatial_layer: int | None = Field(default=None, ge=0, le=2)
    temporal_layer: int | None = Field(default=None, ge=0, le=2)


class EchoTestOk(LooseBaseModel):
    """Successful request result."""

    echotest: Literal["event"]
    result: Literal["ok"]


class EchoTestDone(LooseBaseModel):
    """PeerConnection loss/termination notification."""

    echotest: Literal["event"]
    result: Literal["done"]


class UnknownEchoTestResponse(LooseBaseModel):
    """A future response retained without weakening outbound validation."""

    echotest: str | None = None
    result: Any = None


EchoTestResponse = EchoTestOk | EchoTestDone | UnknownEchoTestResponse
ResponseT = TypeVar("ResponseT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class EchoTestReply(Generic[ResponseT]):
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
    raise EchoTestProtocolError(f"{context} must be a mapping or Pydantic model")


def _error_code(value: Any, *, context: str) -> int:
    if value is None:
        return -1
    if isinstance(value, bool):
        raise EchoTestProtocolError(f"{context} error code must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise EchoTestProtocolError(f"{context} error code must be an integer") from exc


def parse_echotest_response(payload: Any) -> EchoTestReply[EchoTestResponse]:
    """Parse a core Janus response or a bare EchoTest plugin-data object.

    Known responses become precise models. Unknown response variants use a
    permissive model so a newer Janus server does not break older clients.
    """

    outer = _mapping(payload, context="response")
    transaction = outer.get("transaction")
    jsep_payload: Any = None

    if "janus" in outer:
        if outer.get("janus") == "error":
            error = _mapping(outer.get("error"), context="Janus error")
            raise EchoTestJanusError(
                _error_code(error.get("code"), context="Janus"),
                str(error.get("reason", "unknown Janus error")),
                transaction=transaction,
            )
        plugin_data = _mapping(outer.get("plugindata"), context="plugindata")
        plugin = plugin_data.get("plugin")
        if plugin != "janus.plugin.echotest":
            raise EchoTestProtocolError(f"expected janus.plugin.echotest, received {plugin!r}")
        data = _mapping(plugin_data.get("data"), context="plugin data")
        jsep_payload = outer.get("jsep")
    else:
        data = outer

    if "error_code" in data or "error" in data:
        raise EchoTestPluginError(
            _error_code(data.get("error_code"), context="EchoTest"),
            str(data.get("error", "unknown EchoTest error")),
            transaction=transaction,
            raw=data,
        )

    model: type[EchoTestOk | EchoTestDone | UnknownEchoTestResponse]
    result = data.get("result")
    model = (
        {"ok": EchoTestOk, "done": EchoTestDone}.get(result, UnknownEchoTestResponse)
        if isinstance(result, str)
        else UnknownEchoTestResponse
    )
    try:
        parsed = model.model_validate(data)
        jsep = Jsep.model_validate(jsep_payload) if jsep_payload is not None else None
    except ValidationError as exc:
        raise EchoTestProtocolError("invalid EchoTest response") from exc
    return EchoTestReply(data=parsed, jsep=jsep, transaction=transaction, raw=payload)
