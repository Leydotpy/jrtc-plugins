from __future__ import annotations

import asyncio
import builtins
from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypeVar, Unpack

from jrtc.lib import Plugin
from jrtc.models import JanusResponse
from jrtc.models.base import Jsep
from jrtc.models.common import JanusId, validate_janus_id
from jrtc.models.request import TrickleCandidate

from .errors import (
    JanusCommandError,
    StreamingBackendError,
    StreamingProtocolError,
    StreamingTimeout,
)
from .models import (
    ConfigureStream,
    DataTrackSpec,
    FileMountpointSpec,
    IceCandidate,
    RtpMountpointSpec,
    RtspMountpointSpec,
    SessionDescription,
)
from .requests import (
    ConfigureRequest,
    CreateAudioMedia,
    CreateDataMedia,
    CreateMedia,
    CreateRequest,
    CreateVideoMedia,
    DestroyRequest,
    DisableRequest,
    EditRequest,
    EnableRequest,
    InfoRequest,
    KickAllRequest,
    ListRequest,
    MountPoint,
    PauseRequest,
    RecordingMedia,
    RecordingRequest,
    StartRequest,
    StopRequest,
    SwitchRequest,
    WatchRequest,
)
from .requests import ConfigureStream as ProtocolConfigureStream

T = TypeVar("T")


class StreamingPlugin(Plugin):
    """Concrete Streaming handle and typed convenience API.

    ``mountpoint`` and ``admin_key`` are optional convenience defaults.  They
    are package-owned state and never leak into core plugin construction.
    """

    identifier = "streaming"
    name = "janus.plugin.streaming"

    def __init__(
        self,
        *,
        session: Any,
        mountpoint: JanusId | None = None,
        admin_key: str | None = None,
        plugin_id: JanusId | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(session=session, plugin_id=plugin_id, **kwargs)
        self._mountpoint = (
            None if mountpoint is None else validate_janus_id(mountpoint, name="mountpoint")
        )
        self._admin_key = admin_key

    @property
    def mountpoint(self) -> JanusId | None:
        return self._mountpoint

    def _resolve_mountpoint_id(self, mountpoint_id: JanusId | None = None) -> JanusId:
        target = mountpoint_id if mountpoint_id is not None else self._mountpoint
        if target is None:
            raise ValueError("mountpoint ID is required when the plugin is not bound")
        return validate_janus_id(target, name="mountpoint_id")

    async def list(self) -> JanusResponse:
        return await self.send(ListRequest())

    async def info(
        self,
        secret: str | None = None,
        *,
        mountpoint_id: JanusId | None = None,
    ) -> JanusResponse:
        return await self.send(
            InfoRequest(id=self._resolve_mountpoint_id(mountpoint_id), secret=secret)
        )

    async def create(
        self,
        *,
        admin_key: str | None = None,
        **kwargs: Unpack[MountPoint],
    ) -> JanusResponse:
        effective_admin_key = self._admin_key if admin_key is None else admin_key
        payload = CreateRequest.model_validate({"admin_key": effective_admin_key, **kwargs})
        return await self.send(payload)

    async def destroy(
        self,
        *,
        mountpoint_id: JanusId | None = None,
        secret: str | None = None,
        permanent: bool = False,
    ) -> JanusResponse:
        return await self.send(
            DestroyRequest(
                id=self._resolve_mountpoint_id(mountpoint_id),
                permanent=permanent,
                secret=secret,
            )
        )

    async def recording(
        self,
        action: Literal["start", "stop"],
        media: builtins.list[RecordingMedia],
        *,
        mountpoint_id: JanusId | None = None,
    ) -> JanusResponse:
        return await self.send(
            RecordingRequest(
                action=action,
                id=self._resolve_mountpoint_id(mountpoint_id),
                media=media,
            )
        )

    async def edit(
        self,
        *,
        mountpoint_id: JanusId | None = None,
        secret: str | None = None,
        new_description: str | None = None,
        new_metadata: str | None = None,
        new_secret: str | None = None,
        new_pin: str | None = None,
        new_is_private: bool | None = None,
        edited_event: bool = False,
        permanent: bool = False,
    ) -> JanusResponse:
        return await self.send(
            EditRequest(
                id=self._resolve_mountpoint_id(mountpoint_id),
                secret=secret,
                new_description=new_description,
                new_metadata=new_metadata,
                new_secret=new_secret,
                new_pin=new_pin,
                new_is_private=new_is_private,
                edited_event=edited_event,
                permanent=permanent,
            )
        )

    async def enable(
        self,
        *,
        secret: str | None = None,
        mountpoint_id: JanusId | None = None,
    ) -> JanusResponse:
        return await self.send(
            EnableRequest(id=self._resolve_mountpoint_id(mountpoint_id), secret=secret)
        )

    async def disable(
        self,
        *,
        mountpoint_id: JanusId | None = None,
        secret: str | None = None,
        stop_recording: bool = True,
    ) -> JanusResponse:
        return await self.send(
            DisableRequest(
                id=self._resolve_mountpoint_id(mountpoint_id),
                stop_recording=stop_recording,
                secret=secret,
            )
        )

    async def kick_all(
        self,
        *,
        secret: str | None = None,
        mountpoint_id: JanusId | None = None,
    ) -> JanusResponse:
        return await self.send(
            KickAllRequest(id=self._resolve_mountpoint_id(mountpoint_id), secret=secret)
        )

    async def watch(
        self,
        *,
        mountpoint_id: JanusId | None = None,
        pin: str | None = None,
        media: builtins.list[str] | None = None,
        offer_audio: bool | None = None,
        offer_video: bool | None = None,
        offer_data: bool | None = None,
    ) -> JanusResponse:
        return await self.send(
            WatchRequest(
                id=self._resolve_mountpoint_id(mountpoint_id),
                pin=pin,
                media=list(dict.fromkeys(media or ())),
                offer_audio=offer_audio,
                offer_video=offer_video,
                offer_data=offer_data,
            )
        )

    async def start_streaming(self, jsep: Jsep | None = None) -> JanusResponse:
        return await self.send(StartRequest(), jsep=jsep)

    async def pause(self) -> JanusResponse:
        return await self.send(PauseRequest())

    async def configure(self, streams: builtins.list[ProtocolConfigureStream]) -> JanusResponse:
        return await self.send(ConfigureRequest(streams=streams))

    async def switch(self, mountpoint_id: JanusId) -> JanusResponse:
        return await self.send(SwitchRequest(id=mountpoint_id))

    async def stop_streaming(self) -> JanusResponse:
        return await self.send(StopRequest())

    async def subscribe(
        self,
        *,
        mountpoint_id: JanusId | None = None,
        pin: str | None = None,
        media: builtins.list[str] | None = None,
        offer_audio: bool | None = None,
        offer_video: bool | None = None,
        offer_data: bool | None = None,
    ) -> JanusResponse:
        """Alias for :meth:`watch` retained for existing applications."""

        return await self.watch(
            mountpoint_id=mountpoint_id,
            pin=pin,
            media=media,
            offer_audio=offer_audio,
            offer_video=offer_video,
            offer_data=offer_data,
        )


def to_jsonable(value: Any, *, by_alias: bool = True) -> Any:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json", by_alias=by_alias, exclude_none=True)
    if isinstance(value, dict):
        return value
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return {key: item for key, item in attributes.items() if not key.startswith("_")}
    return value


def plugin_payload(response: Any) -> dict[str, Any]:
    if getattr(response, "janus", None) == "error":
        error = getattr(response, "error", None)
        raise JanusCommandError(
            code=getattr(error, "code", None),
            reason=getattr(error, "reason", "unknown Janus error"),
        )
    plugindata = getattr(response, "plugindata", None)
    if plugindata is None:
        raise StreamingProtocolError("expected a Janus plugin response containing plugindata")
    payload = to_jsonable(plugindata.data)
    if not isinstance(payload, dict):
        raise StreamingProtocolError("Janus plugin payload is not an object")
    if "error_code" in payload or ("error" in payload and "status" not in payload):
        raise JanusCommandError(
            code=int(payload["error_code"]) if payload.get("error_code") is not None else None,
            reason=str(payload.get("error") or "Janus Streaming command failed"),
        )
    return payload


def response_jsep(response: Any) -> SessionDescription:
    jsep = getattr(response, "jsep", None)
    if jsep is None:
        payload = plugin_payload(response)
        raw = payload.get("jsep")
        if isinstance(raw, dict):
            return SessionDescription.model_validate(raw)
        raise StreamingProtocolError("Janus watch response did not contain JSEP")
    raw = to_jsonable(jsep)
    return SessionDescription.model_validate(raw)


def list_request() -> ListRequest:
    return ListRequest()


def info_request(mountpoint_id: JanusId, secret: str | None) -> InfoRequest:
    return InfoRequest(id=mountpoint_id, secret=secret)


def rtp_create_request(spec: RtpMountpointSpec, admin_key: str | None) -> CreateRequest:
    media: list[CreateMedia] = []
    for item in spec.media:
        if item.type == "audio":
            media.append(
                CreateAudioMedia(
                    mid=item.mid,
                    msid=item.msid,
                    label=item.label,
                    mcast=item.multicast,
                    iface=item.bind_interface,
                    port=item.port,
                    rtcpport=item.rtcp_port,
                    pt=item.payload_type,
                    codec=item.codec,
                    fmtp=item.fmtp,
                    skew=item.skew,
                )
            )
        elif item.type == "video":
            media.append(
                CreateVideoMedia(
                    mid=item.mid,
                    msid=item.msid,
                    label=item.label,
                    mcast=item.multicast,
                    iface=item.bind_interface,
                    port=item.port,
                    rtcpport=item.rtcp_port,
                    pt=item.payload_type,
                    codec=item.codec,
                    fmtp=item.fmtp,
                    skew=item.skew,
                    simulcast=item.simulcast,
                    port2=item.port2,
                    port3=item.port3,
                    svc=item.svc,
                    h264sps=item.h264_sps,
                    collision=item.collision_ms,
                )
            )
        else:
            data: DataTrackSpec = item
            media.append(
                CreateDataMedia(
                    mid=data.mid,
                    msid=data.msid,
                    label=data.label,
                    mcast=data.multicast,
                    iface=data.bind_interface,
                    port=data.port,
                    datatype=data.data_type,
                    databuffermsg=data.buffer_latest_message,
                )
            )
    return CreateRequest(
        admin_key=admin_key,
        type="rtp",
        id=spec.id,
        name=spec.name,
        description=spec.description,
        metadata=spec.metadata,
        secret=spec.secret,
        pin=spec.pin,
        is_private=spec.private,
        permanent=spec.permanent,
        enabled=spec.enabled,
        media=media,
        threads=spec.threads,
        bufferkf_ms=spec.buffer_keyframes_ms,
        bufferkf_bytes=spec.buffer_keyframes_bytes,
        srtpsuite=spec.srtp_suite,
        srtpcrypto=spec.srtp_crypto,
        e2ee=spec.e2ee,
    )


def rtsp_create_request(spec: RtspMountpointSpec, admin_key: str | None) -> CreateRequest:
    return CreateRequest(
        admin_key=admin_key,
        type="rtsp",
        id=spec.id,
        name=spec.name,
        description=spec.description,
        metadata=spec.metadata,
        secret=spec.secret,
        pin=spec.pin,
        is_private=spec.private,
        permanent=spec.permanent,
        enabled=spec.enabled,
        url=spec.url,
        rtsp_user=spec.username,
        rtsp_pwd=spec.password,
        rtsp_reconnect_delay=spec.reconnect_delay_seconds,
        rtsp_session_timeout=spec.session_timeout_seconds,
        rtsp_timeout=spec.media_timeout_seconds,
        rtsp_conn_timeout=spec.connection_timeout_seconds,
        rtspiface=spec.bind_interface,
        rtsp_notify_changes=spec.notify_changes,
        rtsp_failcheck=spec.fail_check,
        rtsp_quirk=spec.quirk,
    )


def file_create_request(spec: FileMountpointSpec, admin_key: str | None) -> CreateRequest:
    return CreateRequest(
        admin_key=admin_key,
        type=spec.type,
        id=spec.id,
        name=spec.name,
        description=spec.description,
        metadata=spec.metadata,
        secret=spec.secret,
        pin=spec.pin,
        is_private=spec.private,
        permanent=spec.permanent,
        enabled=spec.enabled,
        filename=spec.filename,
        audio=spec.audio,
        video=spec.video,
    )


def destroy_request(mountpoint_id: JanusId, secret: str | None, permanent: bool) -> DestroyRequest:
    return DestroyRequest(id=mountpoint_id, secret=secret, permanent=permanent)


def enable_request(mountpoint_id: JanusId, secret: str | None) -> EnableRequest:
    return EnableRequest(id=mountpoint_id, secret=secret)


def disable_request(
    mountpoint_id: JanusId, secret: str | None, stop_recording: bool
) -> DisableRequest:
    return DisableRequest(id=mountpoint_id, secret=secret, stop_recording=stop_recording)


def kick_all_request(mountpoint_id: JanusId, secret: str | None) -> KickAllRequest:
    return KickAllRequest(id=mountpoint_id, secret=secret)


def edit_request(mountpoint_id: JanusId, **kwargs: Any) -> EditRequest:
    return EditRequest(id=mountpoint_id, **kwargs)


def watch_request(
    mountpoint_id: JanusId,
    *,
    pin: str | None,
    media: list[str],
    offer_audio: bool | None,
    offer_video: bool | None,
    offer_data: bool | None,
) -> WatchRequest:
    return WatchRequest(
        id=mountpoint_id,
        pin=pin,
        media=media,
        offer_audio=offer_audio,
        offer_video=offer_video,
        offer_data=offer_data,
    )


def start_request() -> StartRequest:
    return StartRequest()


def pause_request() -> PauseRequest:
    return PauseRequest()


def stop_request() -> StopRequest:
    return StopRequest()


def switch_request(mountpoint_id: JanusId) -> SwitchRequest:
    return SwitchRequest(id=mountpoint_id)


def configure_request(streams: list[ConfigureStream]) -> ConfigureRequest:
    values = [
        ProtocolConfigureStream(
            mid=item.mid,
            send=item.send,
            substream=item.substream,
            temporal=item.temporal,
            fallback=item.fallback_microseconds,
            spatial_layer=item.spatial_layer,
            temporal_layer=item.temporal_layer,
            min_delay=item.min_delay,
            max_delay=item.max_delay,
        )
        for item in streams
    ]
    return ConfigureRequest(streams=values)


def answer_jsep(answer: SessionDescription) -> Jsep:
    return Jsep(type="answer", sdp=answer.sdp)


def trickle_candidate(candidate: IceCandidate) -> TrickleCandidate:
    return TrickleCandidate(
        candidate=candidate.candidate,
        sdpMid=candidate.sdp_mid,
        sdpMLineIndex=candidate.sdp_mline_index,
    )


def trickle_complete() -> TrickleCandidate:
    return TrickleCandidate(completed=True)


def create_session_manager() -> Any:
    """Create and globally register jrtc's default session manager."""

    from jrtc.conf import Janus
    from jrtc.manager import JanusSessionManager

    manager = JanusSessionManager()
    Janus.set_manager(manager)
    return manager


class JanusStreamingHandle:
    def __init__(self, plugin: Any, *, default_timeout: float) -> None:
        if default_timeout <= 0:
            raise ValueError("default_timeout must be greater than zero")
        self._plugin = plugin
        self._default_timeout = default_timeout
        self._closed = False

    @classmethod
    async def attach(
        cls,
        session: Any,
        *,
        mountpoint_id: JanusId | None = None,
        admin_key: str | None = None,
        attach_timeout: float = 5.0,
        default_timeout: float = 10.0,
        on_event: Callable[[Any], Any] | None = None,
    ) -> JanusStreamingHandle:
        if attach_timeout <= 0:
            raise ValueError("attach_timeout must be greater than zero")
        if default_timeout <= 0:
            raise ValueError("default_timeout must be greater than zero")
        # Mountpoint IDs and the admin key belong in Streaming request bodies,
        # not in core handle construction.  Keep these parameters for the
        # stable high-level factory signature used by admin/viewer clients.
        if mountpoint_id is not None:
            validate_janus_id(mountpoint_id, name="mountpoint_id")
        _ = admin_key
        kwargs: dict[str, Any] = {"session": session}
        if on_event is not None:
            kwargs["on_event"] = on_event
        try:
            async with asyncio.timeout(attach_timeout):
                plugin = await StreamingPlugin(**kwargs).attach()
        except TimeoutError as exc:
            raise StreamingTimeout("attach", attach_timeout) from exc
        except Exception as exc:
            raise StreamingBackendError("could not attach Janus Streaming plugin") from exc
        return cls(plugin, default_timeout=default_timeout)

    @property
    def handle_id(self) -> JanusId:
        return self._plugin.id

    async def request(
        self,
        body: Any,
        *,
        operation: str,
        jsep: Any | None = None,
        timeout_seconds: float | None = None,
    ) -> Any:
        if self._closed:
            raise StreamingBackendError("Janus Streaming handle is closed")
        return await self._run(
            operation,
            self._plugin.send(body, jsep=jsep),
            timeout_seconds=timeout_seconds,
        )

    async def trickle(
        self,
        candidates: list[Any],
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        if self._closed:
            raise StreamingBackendError("Janus Streaming handle is closed")
        return await self._run(
            "trickle",
            self._plugin.trickle(candidates),
            timeout_seconds=timeout_seconds,
        )

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._run("detach", self._plugin.detach(), timeout_seconds=3.0)
        except StreamingBackendError:
            return

    async def _run(
        self,
        operation: str,
        awaitable: Awaitable[T],
        *,
        timeout_seconds: float | None,
    ) -> T:
        effective = timeout_seconds if timeout_seconds is not None else self._default_timeout
        if effective <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        try:
            async with asyncio.timeout(effective):
                return await awaitable
        except TimeoutError as exc:
            raise StreamingTimeout(operation, effective) from exc
        except JanusCommandError:
            raise
        except Exception as exc:
            raise StreamingBackendError(f"Janus Streaming operation {operation!r} failed") from exc
