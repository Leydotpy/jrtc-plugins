from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from contextlib import suppress
from typing import Any

from . import _compat
from .errors import InvalidViewerState, StreamingProtocolError
from .models import (
    ConfigureStream,
    IceCandidate,
    JanusId,
    SessionDescription,
    ViewerState,
    validate_janus_id,
)

HandleFactory = Callable[..., Awaitable[_compat.JanusStreamingHandle]]


class StreamingViewer:
    """One Janus Streaming handle and one browser PeerConnection."""

    def __init__(
        self,
        session: Any,
        *,
        mountpoint_id: JanusId,
        request_timeout: float = 10.0,
        negotiation_timeout: float = 15.0,
        attach_timeout: float = 5.0,
        handle_factory: HandleFactory | None = None,
        on_event: Callable[[Any], Any] | None = None,
    ) -> None:
        mountpoint_id = validate_janus_id(mountpoint_id, name="mountpoint_id")
        if request_timeout <= 0:
            raise ValueError("request_timeout must be greater than zero")
        if negotiation_timeout <= 0:
            raise ValueError("negotiation_timeout must be greater than zero")
        if attach_timeout <= 0:
            raise ValueError("attach_timeout must be greater than zero")
        self.mountpoint_id = mountpoint_id
        self.state = ViewerState.NEW
        self._session = session
        self._request_timeout = request_timeout
        self._negotiation_timeout = negotiation_timeout
        self._attach_timeout = attach_timeout
        self._handle_factory = handle_factory or _compat.JanusStreamingHandle.attach
        self._on_event = on_event
        self._handle: _compat.JanusStreamingHandle | None = None
        self._state_lock = asyncio.Lock()

    async def prepare(
        self,
        *,
        pin: str | None = None,
        media: Iterable[str] = (),
        offer_audio: bool | None = None,
        offer_video: bool | None = None,
        offer_data: bool | None = None,
    ) -> SessionDescription:
        async with self._state_lock:
            self._require_state(ViewerState.NEW)
            selected = list(dict.fromkeys(media))
            self._handle = await self._handle_factory(
                self._session,
                mountpoint_id=self.mountpoint_id,
                attach_timeout=self._attach_timeout,
                default_timeout=self._request_timeout,
                on_event=self._on_event,
            )
            try:
                response = await self._handle.request(
                    _compat.watch_request(
                        self.mountpoint_id,
                        pin=pin,
                        media=selected,
                        offer_audio=offer_audio,
                        offer_video=offer_video,
                        offer_data=offer_data,
                    ),
                    operation="watch",
                    timeout_seconds=self._negotiation_timeout,
                )
                offer = _compat.response_jsep(response)
                if offer.type != "offer":
                    raise StreamingProtocolError("watch response JSEP was not an offer")
                self.state = ViewerState.OFFERED
                return offer
            except BaseException:
                self.state = ViewerState.FAILED
                if self._handle is not None:
                    with suppress(Exception):
                        await asyncio.shield(self._handle.close())
                self._handle = None
                raise

    async def accept_answer(self, answer: SessionDescription) -> None:
        if answer.type != "answer":
            raise ValueError("expected an SDP answer")
        async with self._state_lock:
            self._require_state(ViewerState.OFFERED)
            await self._require_handle().request(
                _compat.start_request(),
                operation="start",
                jsep=_compat.answer_jsep(answer),
                timeout_seconds=self._negotiation_timeout,
            )
            self.state = ViewerState.ACTIVE

    async def add_ice_candidate(self, candidate: IceCandidate) -> None:
        self._require_state(ViewerState.OFFERED, ViewerState.ACTIVE, ViewerState.PAUSED)
        await self._require_handle().trickle([_compat.trickle_candidate(candidate)])

    async def complete_ice(self) -> None:
        self._require_state(ViewerState.OFFERED, ViewerState.ACTIVE, ViewerState.PAUSED)
        await self._require_handle().trickle([_compat.trickle_complete()])

    async def pause(self) -> None:
        async with self._state_lock:
            self._require_state(ViewerState.ACTIVE)
            await self._require_handle().request(_compat.pause_request(), operation="pause")
            self.state = ViewerState.PAUSED

    async def resume(self) -> None:
        async with self._state_lock:
            self._require_state(ViewerState.PAUSED)
            await self._require_handle().request(_compat.start_request(), operation="resume")
            self.state = ViewerState.ACTIVE

    async def configure(self, streams: list[ConfigureStream]) -> None:
        self._require_state(ViewerState.ACTIVE, ViewerState.PAUSED)
        await self._require_handle().request(
            _compat.configure_request(streams),
            operation="configure",
        )

    async def switch(self, mountpoint_id: JanusId) -> None:
        mountpoint_id = validate_janus_id(mountpoint_id, name="mountpoint_id")
        self._require_state(ViewerState.ACTIVE, ViewerState.PAUSED)
        await self._require_handle().request(
            _compat.switch_request(mountpoint_id),
            operation="switch",
        )
        self.mountpoint_id = mountpoint_id

    async def close(self) -> None:
        async with self._state_lock:
            if self.state is ViewerState.CLOSED:
                return
            handle, self._handle = self._handle, None
            previous = self.state
            self.state = ViewerState.CLOSED
        if handle is None:
            return
        if previous in {
            ViewerState.OFFERED,
            ViewerState.ACTIVE,
            ViewerState.PAUSED,
            ViewerState.FAILED,
        }:
            with suppress(Exception):
                await handle.request(_compat.stop_request(), operation="stop", timeout_seconds=3.0)
        with suppress(Exception):
            await handle.close()

    def _require_state(self, *states: ViewerState) -> None:
        if self.state not in states:
            raise InvalidViewerState(self.state, states)

    def _require_handle(self) -> _compat.JanusStreamingHandle:
        if self._handle is None:
            raise StreamingProtocolError("viewer has no attached Janus handle")
        return self._handle
