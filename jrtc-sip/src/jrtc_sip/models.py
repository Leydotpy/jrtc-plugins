"""Strict SIP requests and forward-compatible SIP event parsing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Annotated, Any, Generic, Literal, TypeAlias, TypeVar

from jrtc.models.base import Jsep, PluginMessageBase
from jrtc.models.common import JanusId, LooseBaseModel, StrictBaseModel
from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from .errors import SipJanusError, SipPluginError, SipProtocolError

Headers: TypeAlias = dict[str, str]
ContactParams: TypeAlias = dict[str, str]
SrtpPolicy: TypeAlias = Literal["sdes_optional", "sdes_mandatory"]
StreamType: TypeAlias = Literal["audio", "video", "peer_audio", "peer_video"]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SipStatusName: TypeAlias = Literal[
    "registering",
    "unregistering",
    "subscribing",
    "unsubscribing",
    "calling",
    "proceeding",
    "ringing",
    "progressed",
    "accepting",
    "updating",
    "updated",
    "declining",
    "holding",
    "resuming",
    "hangingup",
    "messagesent",
    "infosent",
    "dtmfsent",
    "transferring",
    "recordingupdated",
    "keyframesent",
]

_SIP_STATUS_EVENTS: frozenset[str] = frozenset(
    {
        "registering",
        "unregistering",
        "subscribing",
        "unsubscribing",
        "calling",
        "proceeding",
        "ringing",
        "progressed",
        "accepting",
        "updating",
        "updated",
        "declining",
        "holding",
        "resuming",
        "hangingup",
        "messagesent",
        "infosent",
        "dtmfsent",
        "transferring",
        "recordingupdated",
        "keyframesent",
    }
)


def _sip_uri(value: Any) -> str:
    """Validate the conservative URI contract accepted by the SIP plugin."""

    if not isinstance(value, str):
        raise ValueError("SIP URI must be a string")
    normalized = value.strip()
    scheme, separator, target = normalized.partition(":")
    if separator != ":" or scheme.lower() not in {"sip", "sips"} or not target:
        raise ValueError("URI must start with sip: or sips: and contain a target")
    if any(character.isspace() for character in normalized):
        raise ValueError("SIP URI must not contain whitespace")
    return normalized


SipUri = Annotated[str, BeforeValidator(_sip_uri)]


class RegisterRequest(PluginMessageBase):
    """Register a normal account, guest identity, or helper handle."""

    request: Literal["register"] = "register"
    type: Literal["guest", "helper"] | None = None
    send_register: bool | None = None
    force_udp: bool | None = None
    force_tcp: bool | None = None
    sips: bool | None = None
    rfc2543_cancel: bool | None = None
    automatic_ringing: bool | None = None
    username: SipUri
    secret: str | None = Field(default=None, min_length=1)
    ha1_secret: str | None = Field(default=None, min_length=1)
    authuser: NonEmptyText | None = None
    display_name: NonEmptyText | None = None
    user_agent: NonEmptyText | None = None
    proxy: SipUri | None = None
    outbound_proxy: SipUri | None = None
    headers: Headers | None = None
    contact_params: ContactParams | None = None
    incoming_header_prefixes: list[NonEmptyText] | None = Field(default=None, min_length=1)
    refresh: bool | None = None
    master_id: JanusId | None = None
    register_ttl: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _registration_mode(self) -> RegisterRequest:
        if self.force_udp is True and self.force_tcp is True:
            raise ValueError("force_udp and force_tcp are mutually exclusive")
        credentials = (self.secret is not None, self.ha1_secret is not None)
        if self.type is None:
            if sum(credentials) != 1:
                raise ValueError("normal registration requires exactly one of secret or ha1_secret")
            if self.master_id is not None:
                raise ValueError("master_id is only valid for helper registration")
        else:
            if any(credentials) or self.authuser is not None:
                raise ValueError("guest/helper registration does not consume credentials")
            if self.type == "guest":
                if self.send_register is True:
                    raise ValueError("guest registration cannot send a SIP REGISTER")
                if self.master_id is not None:
                    raise ValueError("master_id is only valid for helper registration")
            elif self.master_id is None:
                raise ValueError("helper registration requires master_id")
        return self


class UnregisterRequest(PluginMessageBase):
    request: Literal["unregister"] = "unregister"


class CallRequest(PluginMessageBase):
    """Start a SIP INVITE; the outer Janus message must carry an offer."""

    request: Literal["call"] = "call"
    uri: SipUri
    call_id: NonEmptyText | None = None
    refer_id: JanusId | None = None
    headers: Headers | None = None
    srtp: SrtpPolicy | None = None
    srtp_profile: NonEmptyText | None = None
    secret: str | None = Field(default=None, min_length=1)
    ha1_secret: str | None = Field(default=None, min_length=1)
    authuser: NonEmptyText | None = None
    autoaccept_reinvites: bool | None = None

    @model_validator(mode="after")
    def _call_options(self) -> CallRequest:
        if self.secret is not None and self.ha1_secret is not None:
            raise ValueError("secret and ha1_secret are mutually exclusive")
        if self.authuser is not None and self.secret is None and self.ha1_secret is None:
            raise ValueError("authuser requires secret or ha1_secret")
        if self.srtp_profile is not None and self.srtp is None:
            raise ValueError("srtp_profile requires an srtp policy")
        return self


class _AnswerCallRequest(PluginMessageBase):
    srtp: SrtpPolicy | None = None
    srtp_profile: NonEmptyText | None = None
    headers: Headers | None = None
    autoaccept_reinvites: bool | None = None

    @model_validator(mode="after")
    def _srtp_options(self) -> _AnswerCallRequest:
        if self.srtp_profile is not None and self.srtp is None:
            raise ValueError("srtp_profile requires an srtp policy")
        return self


class ProgressRequest(_AnswerCallRequest):
    request: Literal["progress"] = "progress"


class AcceptRequest(_AnswerCallRequest):
    request: Literal["accept"] = "accept"


class UpdateRequest(PluginMessageBase):
    request: Literal["update"] = "update"


class DeclineRequest(PluginMessageBase):
    request: Literal["decline"] = "decline"
    code: int | None = Field(default=None, ge=300, le=699)
    headers: Headers | None = None
    refer_id: JanusId | None = None


class HoldRequest(PluginMessageBase):
    request: Literal["hold"] = "hold"
    direction: Literal["sendonly", "recvonly", "inactive"] | None = None


class UnholdRequest(PluginMessageBase):
    request: Literal["unhold"] = "unhold"


class HangupRequest(PluginMessageBase):
    request: Literal["hangup"] = "hangup"
    headers: Headers | None = None


class MessageRequest(PluginMessageBase):
    request: Literal["message"] = "message"
    call_id: NonEmptyText | None = None
    content_type: NonEmptyText | None = None
    content: str = Field(min_length=1)
    uri: SipUri | None = None
    headers: Headers | None = None


class InfoRequest(PluginMessageBase):
    request: Literal["info"] = "info"
    type: NonEmptyText
    content: str = Field(min_length=1)
    headers: Headers | None = None


class DtmfInfoRequest(PluginMessageBase):
    request: Literal["dtmf_info"] = "dtmf_info"
    digit: str = Field(pattern=r"^[0-9A-Da-d*#]$")
    duration: int | None = Field(default=None, gt=0)
    headers: Headers | None = None


class SubscribeRequest(PluginMessageBase):
    request: Literal["subscribe"] = "subscribe"
    call_id: NonEmptyText | None = None
    event: NonEmptyText
    accept: NonEmptyText | None = None
    to: NonEmptyText | None = None
    subscribe_ttl: int | None = Field(default=None, gt=0)
    content: str | None = Field(default=None, min_length=1)
    content_type: NonEmptyText | None = None
    headers: Headers | None = None

    @model_validator(mode="after")
    def _subscription_body(self) -> SubscribeRequest:
        if (self.content is None) != (self.content_type is None):
            raise ValueError("content and content_type must be supplied together")
        return self


class UnsubscribeRequest(PluginMessageBase):
    request: Literal["unsubscribe"] = "unsubscribe"
    event: NonEmptyText
    to: NonEmptyText | None = None


class TransferRequest(PluginMessageBase):
    request: Literal["transfer"] = "transfer"
    uri: SipUri
    replace: NonEmptyText | None = None


class RecordingRequest(PluginMessageBase):
    request: Literal["recording"] = "recording"
    action: Literal["start", "stop", "pause", "resume"]
    audio: bool | None = None
    video: bool | None = None
    peer_audio: bool | None = None
    peer_video: bool | None = None
    send_peer_pli: bool | None = None
    filename: NonEmptyText | None = None

    @model_validator(mode="after")
    def _has_direction(self) -> RecordingRequest:
        if not any(
            value is True for value in (self.audio, self.video, self.peer_audio, self.peer_video)
        ):
            raise ValueError("select at least one recording direction")
        return self


class KeyframeRequest(PluginMessageBase):
    request: Literal["keyframe"] = "keyframe"
    user: bool | None = None
    peer: bool | None = None

    @model_validator(mode="after")
    def _has_target(self) -> KeyframeRequest:
        if self.user is not True and self.peer is not True:
            raise ValueError("select user, peer, or both")
        return self


class ForwardStream(StrictBaseModel):
    type: StreamType
    host: NonEmptyText
    host_family: Literal["ipv4", "ipv6"] | None = None
    port: int = Field(ge=1, le=65535)
    ssrc: int | None = Field(default=None, ge=1, le=4_294_967_295)
    pt: int | None = Field(default=None, ge=1, le=127)
    srtp_suite: Literal[32, 80] | None = None
    srtp_crypto: NonEmptyText | None = None

    @model_validator(mode="after")
    def _srtp_pair(self) -> ForwardStream:
        if (self.srtp_suite is None) != (self.srtp_crypto is None):
            raise ValueError("srtp_suite and srtp_crypto must be supplied together")
        return self


class RtpForwardRequest(PluginMessageBase):
    request: Literal["rtp_forward"] = "rtp_forward"
    unique_id: NonEmptyText | None = None
    admin_key: str | None = Field(default=None, min_length=1)
    streams: list[ForwardStream] = Field(min_length=1)


class StopRtpForwardRequest(PluginMessageBase):
    request: Literal["stop_rtp_forward"] = "stop_rtp_forward"
    unique_id: NonEmptyText | None = None
    admin_key: str | None = Field(default=None, min_length=1)
    streams: list[JanusId] | None = Field(default=None, min_length=1)
    stream_id: JanusId | None = None

    @model_validator(mode="after")
    def _one_selector(self) -> StopRtpForwardRequest:
        if (self.streams is None) == (self.stream_id is None):
            raise ValueError("provide exactly one of streams or legacy stream_id")
        if self.streams is not None and any(stream_id <= 0 for stream_id in self.streams):
            raise ValueError("stream IDs must be positive")
        return self


class ListForwardersRequest(PluginMessageBase):
    request: Literal["listforwarders"] = "listforwarders"
    unique_id: NonEmptyText | None = None
    admin_key: str | None = Field(default=None, min_length=1)


SipRequest = (
    RegisterRequest
    | UnregisterRequest
    | CallRequest
    | ProgressRequest
    | AcceptRequest
    | UpdateRequest
    | DeclineRequest
    | HoldRequest
    | UnholdRequest
    | HangupRequest
    | MessageRequest
    | InfoRequest
    | DtmfInfoRequest
    | SubscribeRequest
    | UnsubscribeRequest
    | TransferRequest
    | RecordingRequest
    | KeyframeRequest
    | RtpForwardRequest
    | StopRtpForwardRequest
    | ListForwardersRequest
)


class SipResultBase(LooseBaseModel):
    event: str
    headers: Headers | None = None


class SipStatusResult(SipResultBase):
    event: SipStatusName
    call_id: str | None = None
    code: int | None = None
    unique_id: str | None = None


class SipRegisteredResult(SipResultBase):
    event: Literal["registered", "unregistered"]
    username: str
    register_sent: bool | None = None
    master_id: JanusId | None = None
    unique_id: str | None = None
    helper: bool | None = None


class SipFailureResult(SipResultBase):
    event: Literal["registration_failed", "hangup", "subscribe_failed"]
    code: int
    reason: str
    reason_header: str | None = None
    reason_header_protocol: str | None = None
    reason_header_cause: str | None = None


class SipSubscriptionResult(SipResultBase):
    event: Literal["subscribe_succeeded"]
    code: int
    reason: str
    expires: int | None = None


class SipIncomingCallResult(SipResultBase):
    event: Literal["incomingcall", "updatingcall"]
    username: str
    call_id: str | None = None
    displayname: str | None = None
    callee: str | None = None
    referred_by: str | None = None
    replaces: str | None = None
    srtp: SrtpPolicy | None = None
    isfocus: bool | None = None


class SipMissedCallResult(SipResultBase):
    event: Literal["missed_call"]
    caller: str
    displayname: str | None = None
    callee: str | None = None


class SipPeerResult(SipResultBase):
    event: Literal["progress", "accepted"]
    username: str | None = None
    isfocus: bool | None = None


class SipMessageResult(SipResultBase):
    event: Literal["message"]
    sender: str
    displayname: str | None = None
    content_type: str
    content: str


class SipMessageDeliveryResult(SipResultBase):
    event: Literal["messagedelivery"]
    code: int
    reason: str


class SipInfoResult(SipResultBase):
    event: Literal["info"]
    sender: str
    displayname: str | None = None
    type: str
    content: str


class SipNotifyResult(SipResultBase):
    event: Literal["notify"]
    notify: str | None = None
    substate: str | None = None
    content_type: str | None = Field(default=None, alias="content-type")
    content: str


class SipTransferResult(SipResultBase):
    event: Literal["transfer"]
    refer_id: JanusId
    refer_to: str
    referred_by: str | None = None
    replaces: str | None = None


class SipDtmfResult(SipResultBase):
    """An RFC 2833/4733 DTMF event received from the SIP peer."""

    event: Literal["dtmf"]
    sender: str
    signal: str
    duration: int = Field(ge=0)


class SipForwarder(LooseBaseModel):
    stream_id: JanusId
    type: StreamType
    host: str
    port: int
    media: Literal["audio", "video"] | None = None
    ssrc: int | None = None
    pt: int | None = None
    srtp: bool | None = None


class SipRtpForwardResult(SipResultBase):
    event: Literal["rtp_forward"]
    forwarders: list[SipForwarder] = Field(default_factory=list)


class SipStopRtpForwardResult(SipResultBase):
    event: Literal["stop_rtp_forward"]
    stream_id: JanusId | None = None
    streams: list[JanusId] | None = None


class SipForwardersResult(SipResultBase):
    event: Literal["forwarders"]
    rtp_forwarders: list[SipForwarder] = Field(default_factory=list)


class UnknownSipResult(SipResultBase):
    """An event introduced by a future Janus SIP release."""


SipResult = (
    SipStatusResult
    | SipRegisteredResult
    | SipFailureResult
    | SipSubscriptionResult
    | SipIncomingCallResult
    | SipMissedCallResult
    | SipPeerResult
    | SipMessageResult
    | SipMessageDeliveryResult
    | SipInfoResult
    | SipNotifyResult
    | SipTransferResult
    | SipDtmfResult
    | SipRtpForwardResult
    | SipStopRtpForwardResult
    | SipForwardersResult
    | UnknownSipResult
)


class SipEvent(LooseBaseModel):
    sip: Literal["event"]
    call_id: str | None = None
    master_id: JanusId | None = None
    unique_id: str | None = None
    result: SipResult


class UnknownSipResponse(LooseBaseModel):
    sip: str | None = None
    result: Any = None


SipResponse = SipEvent | UnknownSipResponse
ResponseT = TypeVar("ResponseT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class SipReply(Generic[ResponseT]):
    """Typed SIP data and metadata from its outer Janus event."""

    data: ResponseT
    jsep: Jsep | None = None
    transaction: str | None = None
    raw: Any = field(default=None, repr=False, compare=False)


def _mapping(value: Any, *, context: str) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", by_alias=True, exclude_none=False)
    if isinstance(value, Mapping):
        return dict(value)
    raise SipProtocolError(f"{context} must be a mapping or Pydantic model")


def _error_code(value: Any, *, context: str) -> int:
    if value is None:
        return -1
    if isinstance(value, bool):
        raise SipProtocolError(f"{context} error code must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SipProtocolError(f"{context} error code must be an integer") from exc


def _result_model(result: dict[str, Any]) -> BaseModel:
    models: dict[str, type[BaseModel]] = {
        "registered": SipRegisteredResult,
        "unregistered": SipRegisteredResult,
        "registration_failed": SipFailureResult,
        "hangup": SipFailureResult,
        "subscribe_failed": SipFailureResult,
        "subscribe_succeeded": SipSubscriptionResult,
        "incomingcall": SipIncomingCallResult,
        "updatingcall": SipIncomingCallResult,
        "missed_call": SipMissedCallResult,
        "progress": SipPeerResult,
        "accepted": SipPeerResult,
        "message": SipMessageResult,
        "messagedelivery": SipMessageDeliveryResult,
        "info": SipInfoResult,
        "notify": SipNotifyResult,
        "transfer": SipTransferResult,
        "dtmf": SipDtmfResult,
        "rtp_forward": SipRtpForwardResult,
        "stop_rtp_forward": SipStopRtpForwardResult,
        "forwarders": SipForwardersResult,
    }
    event = result.get("event")
    if isinstance(event, str) and event in _SIP_STATUS_EVENTS:
        model: type[BaseModel] = SipStatusResult
    elif isinstance(event, str):
        model = models.get(event, UnknownSipResult)
    else:
        model = UnknownSipResult
    return model.model_validate(result)


def parse_sip_response(payload: Any) -> SipReply[SipResponse]:
    """Parse an outer Janus response or bare SIP plugin-data object."""

    outer = _mapping(payload, context="response")
    transaction = outer.get("transaction")
    jsep_payload: Any = None
    if "janus" in outer:
        if outer.get("janus") == "error":
            error = _mapping(outer.get("error"), context="Janus error")
            raise SipJanusError(
                _error_code(error.get("code"), context="Janus"),
                str(error.get("reason", "unknown Janus error")),
                transaction=transaction,
            )
        plugin_data = _mapping(outer.get("plugindata"), context="plugindata")
        plugin = plugin_data.get("plugin")
        if plugin != "janus.plugin.sip":
            raise SipProtocolError(f"expected janus.plugin.sip, received {plugin!r}")
        data = _mapping(plugin_data.get("data"), context="plugin data")
        jsep_payload = outer.get("jsep")
    else:
        data = outer

    if "error_code" in data or "error" in data:
        raise SipPluginError(
            _error_code(data.get("error_code"), context="SIP"),
            str(data.get("error", "unknown SIP plugin error")),
            transaction=transaction,
            raw=data,
        )

    try:
        if data.get("sip") == "event" and isinstance(data.get("result"), Mapping):
            result = _result_model(dict(data["result"]))
            parsed: SipResponse = SipEvent.model_validate({**data, "result": result})
        else:
            parsed = UnknownSipResponse.model_validate(data)
        jsep = Jsep.model_validate(jsep_payload) if jsep_payload is not None else None
        if jsep is not None and not jsep.sdp.strip():
            raise ValueError("blank JSEP SDP")
    except (ValidationError, ValueError) as exc:
        raise SipProtocolError("invalid SIP response") from exc
    return SipReply(data=parsed, jsep=jsep, transaction=transaction, raw=payload)
