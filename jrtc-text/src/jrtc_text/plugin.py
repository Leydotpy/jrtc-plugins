"""TextRoom handle with intentionally separate Janus and DataChannel paths."""

from __future__ import annotations

from typing import Any, Literal, TypeVar

from jrtc.lib import Plugin
from jrtc.models.base import Jsep

from .datachannel import DataChannelLike, TextRoomDataChannel
from .errors import TextRoomChannelClosed, TextRoomProtocolError
from .models import (
    AckRequest,
    AllowedRequest,
    AnnouncementRequest,
    ChatMessageRequest,
    ControlOk,
    CreateRoomRequest,
    DataChannelRequest,
    DestroyRoomRequest,
    EditRoomRequest,
    JoinRequest,
    KickRequest,
    LeaveRequest,
    ListParticipantsRequest,
    ListRoomsRequest,
    RestartRequest,
    RoomExistsRequest,
    RoomId,
    SetupRequest,
    TextRoomJanusRequest,
    TextRoomReply,
    TextRoomResponse,
    parse_textroom_janus_response,
)

DataRequestT = TypeVar("DataRequestT", bound=DataChannelRequest)


def _answer(value: Jsep) -> Jsep:
    if value.type != "answer":
        raise TextRoomProtocolError("TextRoom ack requires a JSEP answer")
    if not value.sdp.strip():
        raise TextRoomProtocolError("JSEP SDP must not be blank")
    return value


def _required_response(response: TextRoomResponse | None) -> TextRoomResponse:
    if response is None:
        raise TextRoomProtocolError("TextRoom request unexpectedly disabled its response")
    return response


def _use_transaction(request: DataRequestT, transaction: str | None) -> DataRequestT:
    """Apply an optional caller transaction while preserving validation."""

    if transaction is not None:
        request.transaction = transaction
    return request


class TextRoomPlugin(Plugin):
    """Typed handle for ``janus.plugin.textroom``."""

    identifier = "textroom"
    name = "janus.plugin.textroom"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._datachannel: TextRoomDataChannel | None = None

    @property
    def datachannel(self) -> TextRoomDataChannel:
        if self._datachannel is None:
            raise TextRoomChannelClosed("no DataChannel has been bound")
        return self._datachannel

    def bind_datachannel(
        self,
        channel: DataChannelLike,
        *,
        default_timeout: float = 10.0,
        max_pending: int = 256,
        max_events: int = 512,
        max_message_bytes: int = 1_048_576,
    ) -> TextRoomDataChannel:
        """Bind one channel and create its bounded transaction manager."""

        if self._datachannel is not None and not self._datachannel.closed:
            raise RuntimeError("close the current TextRoom DataChannel before rebinding")
        manager = TextRoomDataChannel(
            channel,
            default_timeout=default_timeout,
            max_pending=max_pending,
            max_events=max_events,
            max_message_bytes=max_message_bytes,
        )
        self._datachannel = manager
        return manager

    def feed_datachannel(self, payload: str | bytes | bytearray | memoryview) -> TextRoomResponse:
        """Route one incoming channel payload to transactions or event backlog."""

        return self.datachannel.feed_data(payload)

    async def _janus_request(
        self,
        body: TextRoomJanusRequest,
        *,
        jsep: Jsep | None = None,
        synchronous: bool,
        timeout: float | None = None,
    ) -> TextRoomReply[TextRoomResponse]:
        response = await super().send(
            body,
            jsep,
            timeout=timeout,
            wait_for_event=not synchronous,
        )
        return parse_textroom_janus_response(response)

    async def setup(self, *, timeout: float | None = None) -> TextRoomReply[TextRoomResponse]:
        """Ask Janus to originate the data-only PeerConnection offer."""

        reply = await self._janus_request(SetupRequest(), synchronous=False, timeout=timeout)
        if not isinstance(reply.data, ControlOk):
            raise TextRoomProtocolError("setup did not return the expected ok event")
        if reply.jsep is None or reply.jsep.type != "offer" or not reply.jsep.sdp.strip():
            raise TextRoomProtocolError("setup must return a JSEP offer")
        return reply

    async def restart(self, *, timeout: float | None = None) -> TextRoomReply[TextRoomResponse]:
        """Ask Janus for an ICE-restart offer."""

        reply = await self._janus_request(RestartRequest(), synchronous=False, timeout=timeout)
        if not isinstance(reply.data, ControlOk):
            raise TextRoomProtocolError("restart did not return the expected ok event")
        if (
            reply.jsep is None
            or reply.jsep.type != "offer"
            or reply.jsep.restart is not True
            or not reply.jsep.sdp.strip()
        ):
            raise TextRoomProtocolError("restart must return a restart-marked JSEP offer")
        return reply

    async def ack(
        self, answer: Jsep, *, timeout: float | None = None
    ) -> TextRoomReply[TextRoomResponse]:
        """Complete setup/restart with the application's JSEP answer."""

        reply = await self._janus_request(
            AckRequest(),
            jsep=_answer(answer),
            synchronous=False,
            timeout=timeout,
        )
        if not isinstance(reply.data, ControlOk):
            raise TextRoomProtocolError("ack did not return the expected ok event")
        if reply.jsep is not None:
            raise TextRoomProtocolError("ack must not return another JSEP description")
        return reply

    # Synchronous room administration over the Janus request surface.
    async def list_rooms(
        self,
        *,
        admin_key: str | None = None,
        timeout: float | None = None,
    ) -> TextRoomReply[TextRoomResponse]:
        """List public rooms synchronously through the Janus API."""

        return await self._janus_request(
            ListRoomsRequest(admin_key=admin_key),
            synchronous=True,
            timeout=timeout,
        )

    async def list_participants(
        self, room: RoomId, *, timeout: float | None = None
    ) -> TextRoomReply[TextRoomResponse]:
        """List the current participants in one room over Janus."""

        return await self._janus_request(
            ListParticipantsRequest(room=room),
            synchronous=True,
            timeout=timeout,
        )

    async def create_room(
        self,
        *,
        room: RoomId | None = None,
        admin_key: str | None = None,
        description: str | None = None,
        secret: str | None = None,
        pin: str | None = None,
        post: str | None = None,
        is_private: bool | None = None,
        history: int | None = None,
        allowed: list[str] | None = None,
        permanent: bool | None = None,
        timeout: float | None = None,
    ) -> TextRoomReply[TextRoomResponse]:
        """Create a dynamic or permanent room over the Janus API."""

        body = CreateRoomRequest(
            room=room,
            admin_key=admin_key,
            description=description,
            secret=secret,
            pin=pin,
            post=post,
            is_private=is_private,
            history=history,
            allowed=allowed,
            permanent=permanent,
        )
        return await self._janus_request(body, synchronous=True, timeout=timeout)

    async def edit_room(
        self,
        room: RoomId,
        *,
        secret: str | None = None,
        new_description: str | None = None,
        new_secret: str | None = None,
        new_pin: str | None = None,
        new_post: str | None = None,
        new_is_private: bool | None = None,
        permanent: bool | None = None,
        timeout: float | None = None,
    ) -> TextRoomReply[TextRoomResponse]:
        """Edit mutable room configuration over the Janus API."""

        body = EditRoomRequest(
            room=room,
            secret=secret,
            new_description=new_description,
            new_secret=new_secret,
            new_pin=new_pin,
            new_post=new_post,
            new_is_private=new_is_private,
            permanent=permanent,
        )
        return await self._janus_request(body, synchronous=True, timeout=timeout)

    async def destroy_room(
        self,
        room: RoomId,
        *,
        secret: str | None = None,
        permanent: bool | None = None,
        timeout: float | None = None,
    ) -> TextRoomReply[TextRoomResponse]:
        """Destroy a room and optionally remove its persisted configuration."""

        body = DestroyRoomRequest(room=room, secret=secret, permanent=permanent)
        return await self._janus_request(body, synchronous=True, timeout=timeout)

    async def room_exists(
        self, room: RoomId, *, timeout: float | None = None
    ) -> TextRoomReply[TextRoomResponse]:
        """Check synchronously whether a room exists."""

        return await self._janus_request(
            RoomExistsRequest(room=room), synchronous=True, timeout=timeout
        )

    async def allowed(
        self,
        room: RoomId,
        action: Literal["enable", "disable", "add", "remove"],
        *,
        secret: str | None = None,
        tokens: list[str] | None = None,
        timeout: float | None = None,
    ) -> TextRoomReply[TextRoomResponse]:
        """Enable, disable, add to, or remove from a room token ACL."""

        body = AllowedRequest(
            room=room,
            action=action,
            secret=secret,
            allowed=tokens,
        )
        return await self._janus_request(body, synchronous=True, timeout=timeout)

    # Participation always uses the DataChannel transaction surface.
    async def join(
        self,
        room: RoomId,
        username: str,
        *,
        pin: str | None = None,
        display: str | None = None,
        token: str | None = None,
        history: bool | None = None,
        transaction: str | None = None,
        timeout: float | None = None,
    ) -> TextRoomResponse:
        """Join a room through the bound DataChannel and await correlation."""

        request = _use_transaction(
            JoinRequest(
                room=room,
                username=username,
                pin=pin,
                display=display,
                token=token,
                history=history,
            ),
            transaction,
        )
        response = await self.datachannel.request(request, timeout=timeout)
        return _required_response(response)

    async def leave(
        self,
        room: RoomId,
        *,
        transaction: str | None = None,
        timeout: float | None = None,
    ) -> TextRoomResponse:
        """Leave one joined room through the bound DataChannel."""

        request = _use_transaction(LeaveRequest(room=room), transaction)
        response = await self.datachannel.request(request, timeout=timeout)
        return _required_response(response)

    async def message(
        self,
        room: RoomId,
        text: str,
        *,
        to: str | None = None,
        tos: list[str] | None = None,
        ack: bool | None = None,
        transaction: str | None = None,
        timeout: float | None = None,
    ) -> TextRoomResponse | None:
        """Send public/private text; ``ack=False`` returns without waiting."""

        request = _use_transaction(
            ChatMessageRequest(room=room, text=text, to=to, tos=tos, ack=ack),
            transaction,
        )
        return await self.datachannel.request(request, timeout=timeout)

    async def announcement(
        self,
        room: RoomId,
        text: str,
        *,
        secret: str | None = None,
        transaction: str | None = None,
        timeout: float | None = None,
    ) -> TextRoomResponse:
        """Send a room-authenticated announcement through the DataChannel."""

        request = _use_transaction(
            AnnouncementRequest(room=room, text=text, secret=secret),
            transaction,
        )
        response = await self.datachannel.request(request, timeout=timeout)
        return _required_response(response)

    async def kick(
        self,
        room: RoomId,
        username: str,
        *,
        secret: str | None = None,
        transaction: str | None = None,
        timeout: float | None = None,
    ) -> TextRoomResponse:
        """Kick a participant through the authenticated DataChannel request."""

        request = _use_transaction(
            KickRequest(room=room, username=username, secret=secret),
            transaction,
        )
        response = await self.datachannel.request(request, timeout=timeout)
        return _required_response(response)

    async def aclose(self) -> None:
        """Close pending DataChannel transactions, then detach the Janus handle."""

        if self._datachannel is not None:
            await self._datachannel.aclose()
        await super().aclose()
