"""Separate Janus-control and DataChannel wire models for TextRoom."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Annotated, Any, Generic, Literal, TypeAlias, TypeVar
from uuid import uuid4

from jrtc.models.base import Jsep, PluginMessageBase
from jrtc.models.common import JanusId, LooseBaseModel, StrictBaseModel
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from .errors import (
    TextRoomJanusError,
    TextRoomPluginError,
    TextRoomProtocolError,
)

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


RoomId: TypeAlias = JanusId


# Janus plugin-message surface -------------------------------------------------
class SetupRequest(PluginMessageBase):
    request: Literal["setup"] = "setup"


class AckRequest(PluginMessageBase):
    request: Literal["ack"] = "ack"


class RestartRequest(PluginMessageBase):
    request: Literal["restart"] = "restart"


class ListRoomsRequest(PluginMessageBase):
    request: Literal["list"] = "list"
    admin_key: str | None = Field(default=None, min_length=1)


class ListParticipantsRequest(PluginMessageBase):
    request: Literal["listparticipants"] = "listparticipants"
    room: RoomId


class CreateRoomRequest(PluginMessageBase):
    request: Literal["create"] = "create"
    room: RoomId | None = None
    admin_key: str | None = Field(default=None, min_length=1)
    description: NonEmptyText | None = None
    secret: str | None = Field(default=None, min_length=1)
    pin: str | None = Field(default=None, min_length=1)
    post: NonEmptyText | None = None
    is_private: bool | None = None
    history: int | None = Field(default=None, gt=0)
    allowed: list[NonEmptyText] | None = None
    permanent: bool | None = None


class EditRoomRequest(PluginMessageBase):
    request: Literal["edit"] = "edit"
    room: RoomId
    secret: str | None = Field(default=None, min_length=1)
    new_description: NonEmptyText | None = None
    new_secret: str | None = Field(default=None, min_length=1)
    new_pin: str | None = Field(default=None, min_length=1)
    new_post: NonEmptyText | None = None
    new_is_private: bool | None = None
    permanent: bool | None = None

    @model_validator(mode="after")
    def _has_change(self) -> EditRoomRequest:
        if all(
            value is None
            for value in (
                self.new_description,
                self.new_secret,
                self.new_pin,
                self.new_post,
                self.new_is_private,
                self.permanent,
            )
        ):
            raise ValueError("edit requires at least one changed property")
        return self


class DestroyRoomRequest(PluginMessageBase):
    request: Literal["destroy"] = "destroy"
    room: RoomId
    secret: str | None = Field(default=None, min_length=1)
    permanent: bool | None = None


class RoomExistsRequest(PluginMessageBase):
    request: Literal["exists"] = "exists"
    room: RoomId


class AllowedRequest(PluginMessageBase):
    request: Literal["allowed"] = "allowed"
    room: RoomId
    secret: str | None = Field(default=None, min_length=1)
    action: Literal["enable", "disable", "add", "remove"]
    allowed: list[NonEmptyText] | None = None

    @model_validator(mode="after")
    def _tokens_for_mutation(self) -> AllowedRequest:
        if self.action in {"add", "remove"} and not self.allowed:
            raise ValueError("add/remove requires at least one token")
        if self.action in {"enable", "disable"} and self.allowed is not None:
            raise ValueError("allowed tokens are only valid for add/remove")
        return self


TextRoomJanusRequest = (
    SetupRequest
    | AckRequest
    | RestartRequest
    | ListRoomsRequest
    | ListParticipantsRequest
    | CreateRoomRequest
    | EditRoomRequest
    | DestroyRoomRequest
    | RoomExistsRequest
    | AllowedRequest
)


# DataChannel surface ----------------------------------------------------------
def _transaction() -> str:
    return uuid4().hex


class DataChannelRequest(StrictBaseModel):
    """Base for TextRoom messages that must never enter the Janus body."""

    textroom: str
    transaction: str = Field(default_factory=_transaction, min_length=1)


class JoinRequest(DataChannelRequest):
    textroom: Literal["join"] = "join"
    room: RoomId
    username: NonEmptyText
    pin: str | None = Field(default=None, min_length=1)
    display: NonEmptyText | None = None
    token: str | None = Field(default=None, min_length=1)
    history: bool | None = None


class LeaveRequest(DataChannelRequest):
    textroom: Literal["leave"] = "leave"
    room: RoomId


class ChatMessageRequest(DataChannelRequest):
    textroom: Literal["message"] = "message"
    room: RoomId
    text: str = Field(min_length=1)
    to: NonEmptyText | None = None
    tos: list[NonEmptyText] | None = Field(default=None, min_length=1)
    ack: bool | None = None

    @model_validator(mode="after")
    def _one_recipient_form(self) -> ChatMessageRequest:
        if self.to is not None and self.tos is not None:
            raise ValueError("to and tos are mutually exclusive")
        return self


class AnnouncementRequest(DataChannelRequest):
    textroom: Literal["announcement"] = "announcement"
    room: RoomId
    secret: str | None = Field(default=None, min_length=1)
    text: str = Field(min_length=1)


class KickRequest(DataChannelRequest):
    textroom: Literal["kick"] = "kick"
    room: RoomId
    secret: str | None = Field(default=None, min_length=1)
    username: NonEmptyText


TextRoomDataRequest = (
    JoinRequest | LeaveRequest | ChatMessageRequest | AnnouncementRequest | KickRequest
)


# Shared inbound data ----------------------------------------------------------
class RoomSummary(LooseBaseModel):
    room: RoomId
    description: str
    pin_required: bool | None = None
    num_participants: int | None = None
    history: int | None = None


class Participant(LooseBaseModel):
    username: str
    display: str | None = None


class ControlOk(LooseBaseModel):
    textroom: Literal["event"]
    result: Literal["ok"]


class SuccessResponse(LooseBaseModel):
    textroom: Literal["success"]
    transaction: str | None = None
    room: RoomId | None = None
    permanent: bool | None = None
    exists: bool | None = None
    allowed: list[str] | None = None
    rooms: list[RoomSummary] | None = Field(default=None, alias="list")
    participants: list[Participant] | None = None
    sent: dict[str, bool] | None = None


class CreatedResponse(LooseBaseModel):
    """Janus-API response to synchronous room creation."""

    textroom: Literal["created"]
    room: RoomId
    permanent: bool | None = None


class EditedResponse(LooseBaseModel):
    textroom: Literal["edited"]
    transaction: str | None = None
    room: RoomId
    permanent: bool | None = None


class DestroyedResponse(LooseBaseModel):
    textroom: Literal["destroyed"]
    transaction: str | None = None
    room: RoomId
    permanent: bool | None = None


class JoinEvent(LooseBaseModel):
    textroom: Literal["join"]
    room: RoomId
    username: str
    display: str | None = None


class LeaveEvent(LooseBaseModel):
    textroom: Literal["leave"]
    room: RoomId
    username: str


class KickedEvent(LooseBaseModel):
    textroom: Literal["kicked"]
    room: RoomId
    username: str


class MessageEvent(LooseBaseModel):
    textroom: Literal["message"]
    room: RoomId
    from_: str = Field(alias="from")
    date: str
    text: str
    whisper: bool | None = None
    display: str | None = None


class AnnouncementEvent(LooseBaseModel):
    textroom: Literal["announcement"]
    room: RoomId
    date: str
    text: str


class TextRoomErrorResponse(LooseBaseModel):
    textroom: Literal["error", "event"]
    error_code: int
    error: str
    transaction: str | None = None


class UnknownTextRoomResponse(LooseBaseModel):
    textroom: str | None = None
    transaction: str | None = None


TextRoomResponse = (
    ControlOk
    | SuccessResponse
    | CreatedResponse
    | EditedResponse
    | DestroyedResponse
    | JoinEvent
    | LeaveEvent
    | KickedEvent
    | MessageEvent
    | AnnouncementEvent
    | TextRoomErrorResponse
    | UnknownTextRoomResponse
)
ResponseT = TypeVar("ResponseT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class TextRoomReply(Generic[ResponseT]):
    data: ResponseT
    jsep: Jsep | None = None
    transaction: str | None = None
    raw: Any = field(default=None, repr=False, compare=False)


def _mapping(value: Any, *, context: str) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", by_alias=True, exclude_none=False)
    if isinstance(value, Mapping):
        return dict(value)
    raise TextRoomProtocolError(f"{context} must be a mapping or Pydantic model")


def _error_code(value: Any, *, context: str) -> int:
    if isinstance(value, bool):
        raise TextRoomProtocolError(f"{context} error code must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TextRoomProtocolError(f"{context} error code must be an integer") from exc


_TEXTROOM_MODELS: dict[str, type[BaseModel]] = {
    "success": SuccessResponse,
    "created": CreatedResponse,
    "edited": EditedResponse,
    "destroyed": DestroyedResponse,
    "join": JoinEvent,
    "leave": LeaveEvent,
    "kicked": KickedEvent,
    "message": MessageEvent,
    "announcement": AnnouncementEvent,
}


def parse_textroom_data_response(payload: Any, *, raise_errors: bool = True) -> TextRoomResponse:
    """Parse one bare UTF-8 DataChannel/room-management response."""

    data = _mapping(payload, context="TextRoom data")
    if "error_code" in data or "error" in data:
        try:
            parsed_error = TextRoomErrorResponse.model_validate(data)
        except ValidationError as exc:
            raise TextRoomProtocolError("invalid TextRoom error response") from exc
        if raise_errors:
            raise TextRoomPluginError(
                parsed_error.error_code,
                parsed_error.error,
                transaction=parsed_error.transaction,
                raw=data,
            )
        return parsed_error
    kind = data.get("textroom")
    if kind == "event" and data.get("result") == "ok":
        model: type[BaseModel] = ControlOk
    elif isinstance(kind, str):
        model = _TEXTROOM_MODELS.get(kind, UnknownTextRoomResponse)
    else:
        model = UnknownTextRoomResponse
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise TextRoomProtocolError("invalid TextRoom response") from exc


def parse_textroom_janus_response(payload: Any) -> TextRoomReply[TextRoomResponse]:
    """Parse a core Janus response containing TextRoom plugin data."""

    outer = _mapping(payload, context="response")
    transaction = outer.get("transaction")
    if "janus" not in outer:
        data = outer
        jsep_payload: Any = None
    else:
        if outer.get("janus") == "error":
            error = _mapping(outer.get("error"), context="Janus error")
            raise TextRoomJanusError(
                _error_code(error.get("code"), context="Janus"),
                str(error.get("reason", "unknown Janus error")),
                transaction=transaction,
            )
        plugin_data = _mapping(outer.get("plugindata"), context="plugindata")
        plugin = plugin_data.get("plugin")
        if plugin != "janus.plugin.textroom":
            raise TextRoomProtocolError(f"expected janus.plugin.textroom, received {plugin!r}")
        data = _mapping(plugin_data.get("data"), context="plugin data")
        jsep_payload = outer.get("jsep")
    parsed = parse_textroom_data_response(data)
    try:
        jsep = Jsep.model_validate(jsep_payload) if jsep_payload is not None else None
        if jsep is not None and not jsep.sdp.strip():
            raise ValueError("blank JSEP SDP")
    except ValidationError as exc:
        raise TextRoomProtocolError("invalid TextRoom JSEP") from exc
    except ValueError as exc:
        raise TextRoomProtocolError("invalid TextRoom JSEP") from exc
    return TextRoomReply(data=parsed, jsep=jsep, transaction=transaction, raw=payload)
