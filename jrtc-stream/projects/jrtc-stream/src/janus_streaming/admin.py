from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from . import _compat
from .errors import StreamingNotStarted, StreamingProtocolError
from .models import (
    CreatedMountpoint,
    FileMountpointSpec,
    JanusId,
    MountpointInfo,
    MountpointSummary,
    RtpMountpointSpec,
    RtspMountpointSpec,
)

HandleFactory = Callable[..., Awaitable[_compat.JanusStreamingHandle]]


class StreamingAdminClient:
    def __init__(
        self,
        session: Any,
        *,
        admin_key: str | None = None,
        request_timeout: float = 10.0,
        attach_timeout: float = 5.0,
        max_concurrency: int = 32,
        handle_factory: HandleFactory | None = None,
    ) -> None:
        if request_timeout <= 0:
            raise ValueError("request_timeout must be greater than zero")
        if attach_timeout <= 0:
            raise ValueError("attach_timeout must be greater than zero")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least one")
        self._session = session
        self._admin_key = admin_key
        self._request_timeout = request_timeout
        self._attach_timeout = attach_timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._start_lock = asyncio.Lock()
        self._handle: _compat.JanusStreamingHandle | None = None
        self._handle_factory = handle_factory or _compat.JanusStreamingHandle.attach

    async def start(self) -> None:
        async with self._start_lock:
            if self._handle is not None:
                return
            self._handle = await self._handle_factory(
                self._session,
                admin_key=self._admin_key,
                attach_timeout=self._attach_timeout,
                default_timeout=self._request_timeout,
            )

    async def close(self) -> None:
        handle, self._handle = self._handle, None
        if handle is not None:
            await handle.close()

    async def list_mountpoints(self) -> tuple[MountpointSummary, ...]:
        payload = await self._command(_compat.list_request(), "list")
        values = payload.get("list", payload.get("mountpoints", []))
        if not isinstance(values, list):
            raise StreamingProtocolError("list response did not contain a mountpoint list")
        return tuple(self._parse_summary(item) for item in values)

    async def info(self, mountpoint_id: JanusId, *, secret: str | None = None) -> MountpointInfo:
        payload = await self._command(
            _compat.info_request(mountpoint_id, secret),
            "info",
        )
        value = payload.get("info", payload.get("mountpoint"))
        if not isinstance(value, dict):
            raise StreamingProtocolError("info response did not contain mountpoint information")
        return self._parse_info(value)

    async def create_rtp(self, spec: RtpMountpointSpec) -> CreatedMountpoint:
        return await self._create(_compat.rtp_create_request(spec, self._admin_key))

    async def create_rtsp(self, spec: RtspMountpointSpec) -> CreatedMountpoint:
        return await self._create(_compat.rtsp_create_request(spec, self._admin_key))

    async def create_file(self, spec: FileMountpointSpec) -> CreatedMountpoint:
        return await self._create(_compat.file_create_request(spec, self._admin_key))

    async def edit(
        self,
        mountpoint_id: JanusId,
        *,
        secret: str | None = None,
        new_description: str | None = None,
        new_metadata: str | None = None,
        new_secret: str | None = None,
        new_pin: str | None = None,
        new_private: bool | None = None,
        permanent: bool = False,
        edited_event: bool = False,
    ) -> dict[str, Any]:
        return await self._command(
            _compat.edit_request(
                mountpoint_id,
                secret=secret,
                new_description=new_description,
                new_metadata=new_metadata,
                new_secret=new_secret,
                new_pin=new_pin,
                new_is_private=new_private,
                permanent=permanent,
                edited_event=edited_event,
            ),
            "edit",
        )

    async def enable(self, mountpoint_id: JanusId, *, secret: str | None = None) -> None:
        await self._command(_compat.enable_request(mountpoint_id, secret), "enable")

    async def disable(
        self,
        mountpoint_id: JanusId,
        *,
        secret: str | None = None,
        stop_recording: bool = True,
    ) -> None:
        await self._command(
            _compat.disable_request(mountpoint_id, secret, stop_recording),
            "disable",
        )

    async def kick_all(self, mountpoint_id: JanusId, *, secret: str | None = None) -> None:
        await self._command(_compat.kick_all_request(mountpoint_id, secret), "kick_all")

    async def destroy(
        self,
        mountpoint_id: JanusId,
        *,
        secret: str | None = None,
        permanent: bool = False,
    ) -> None:
        await self._command(
            _compat.destroy_request(mountpoint_id, secret, permanent),
            "destroy",
        )

    async def _create(self, request: Any) -> CreatedMountpoint:
        payload = await self._command(request, "create")
        value = payload.get("stream")
        if not isinstance(value, dict):
            raise StreamingProtocolError("create response did not contain a stream")
        normalized = dict(value)
        normalized["private"] = normalized.pop("is_private", normalized.get("private"))
        normalized["permanent"] = bool(payload.get("permanent", False))
        return CreatedMountpoint.model_validate(normalized)

    async def _command(self, request: Any, operation: str) -> dict[str, Any]:
        handle = self._require_handle()
        async with self._semaphore:
            response = await handle.request(request, operation=operation)
        return _compat.plugin_payload(response)

    def _require_handle(self) -> _compat.JanusStreamingHandle:
        if self._handle is None:
            raise StreamingNotStarted("StreamingAdminClient.start() has not been called")
        return self._handle

    @staticmethod
    def _parse_summary(value: Any) -> MountpointSummary:
        if not isinstance(value, dict):
            value = _compat.to_jsonable(value)
        normalized = dict(value)
        normalized["media"] = [
            StreamingAdminClient._normalize_track(item) for item in value.get("media", [])
        ]
        return MountpointSummary.model_validate(normalized)

    @staticmethod
    def _parse_info(value: Any) -> MountpointInfo:
        if not isinstance(value, dict):
            value = _compat.to_jsonable(value)
        normalized = dict(value)
        normalized["private"] = normalized.pop("is_private", normalized.get("private"))
        normalized.pop("secret", None)
        normalized.pop("pin", None)
        normalized["media"] = [
            StreamingAdminClient._normalize_track(item) for item in value.get("media", [])
        ]
        return MountpointInfo.model_validate(normalized)

    @staticmethod
    def _normalize_track(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            value = _compat.to_jsonable(value)
        normalized = dict(value)
        normalized["payload_type"] = normalized.pop("pt", normalized.get("payload_type"))
        normalized["port"] = normalized.get("port", normalized.get("rtp_port"))
        allowed = {
            "mid",
            "type",
            "label",
            "msid",
            "mindex",
            "age_ms",
            "payload_type",
            "codec",
            "rtpmap",
            "fmtp",
            "port",
        }
        return {key: item for key, item in normalized.items() if key in allowed}
