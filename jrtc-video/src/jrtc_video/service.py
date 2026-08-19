"""Lifecycle-managed VideoRoom publisher and subscriber orchestration.

This module intentionally has no process-global state and no synchronous loop
runner. Every object lives on the caller's current asyncio loop and the service
owns only the plugin handles it creates, never the Janus session itself.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Hashable, Self

from jrtc.models.base import Jsep
from jrtc.models.common import JanusId

from .errors import VideoRoomLifecycleError, VideoRoomProtocolError
from .models import (
    PublisherConfigureRequest,
    PublisherJoinRequest,
    PublisherPublishRequest,
    SubscribeTarget,
    SubscriberConfigureRequest,
    SubscriberJoinRequest,
    SubscriberStreamControl,
    SubscriberSubscribeRequest,
    SubscriberSwitchRequest,
    SubscriberUnsubscribeRequest,
    SubscriberUpdateRequest,
    SwitchTarget,
    UnsubscribeTarget,
    VideoRoomAttached,
    VideoRoomCreateRequest,
    VideoRoomDestroyRequest,
    VideoRoomJoined,
    VideoRoomReply,
    VideoRoomResponse,
)
from .plugin import VideoRoomPlugin

@dataclass(slots=True)
class Publisher:
    """One service-owned publisher handle and its role state."""

    plugin: VideoRoomPlugin
    room: JanusId
    participant: JanusId
    private_id: JanusId | None = None
    _published: bool = field(default=False, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def published(self) -> bool:
        return self._published

    @property
    def closed(self) -> bool:
        return self._closed

    def _ensure_open(self) -> None:
        if self._closed:
            raise VideoRoomLifecycleError("publisher is closed")

    async def publish_offer(
        self,
        offer: Jsep,
        *,
        settings: PublisherPublishRequest | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        """Publish once, then safely use configure for later offers.

        Janus rejects a second ``publish`` on an already active handle. This
        preserves the useful old facade behavior while keeping state local to
        this publisher object.
        """

        self._ensure_open()
        settings = settings or PublisherPublishRequest()
        if not self._published:
            reply = await self.plugin.publish(offer, body=settings, timeout=timeout)
            self._published = True
            return reply

        values = settings.model_dump(
            mode="python",
            exclude={"request"},
            exclude_none=True,
            exclude_unset=True,
        )
        configure = PublisherConfigureRequest.model_validate(values)
        return await self.plugin.configure_publisher(
            configure, offer=offer, timeout=timeout
        )

    async def configure(
        self,
        settings: PublisherConfigureRequest,
        *,
        offer: Jsep | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        self._ensure_open()
        return await self.plugin.configure_publisher(
            settings, offer=offer, timeout=timeout
        )

    async def unpublish(
        self, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse] | None:
        self._ensure_open()
        if not self._published:
            return None
        reply = await self.plugin.unpublish(timeout=timeout)
        self._published = False
        return reply

    async def trickle(self, candidates: Any, *, timeout: float | None = None) -> Any:
        self._ensure_open()
        return await self.plugin.trickle(candidates, timeout=timeout)

    async def complete_trickle(self, *, timeout: float | None = None) -> Any:
        self._ensure_open()
        return await self.plugin.complete_trickle(timeout=timeout)

    async def aclose(self, *, graceful: bool = True) -> None:
        if self._closed:
            return
        self._closed = True
        failures: list[Exception] = []
        if graceful:
            try:
                await self.plugin.leave()
            except Exception as exc:
                failures.append(exc)
        try:
            await self.plugin.detach()
        except Exception as exc:
            failures.append(exc)
        self._published = False
        if failures:
            raise ExceptionGroup("failed to close VideoRoom publisher", failures)


@dataclass(slots=True)
class Subscriber:
    """One service-owned multistream subscriber handle."""

    plugin: VideoRoomPlugin
    room: JanusId
    owner: JanusId
    key: Hashable
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def closed(self) -> bool:
        return self._closed

    def _ensure_open(self) -> None:
        if self._closed:
            raise VideoRoomLifecycleError("subscriber is closed")

    async def start(
        self,
        *,
        answer: Jsep | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        self._ensure_open()
        return await self.plugin.start(answer=answer, timeout=timeout)

    async def pause(
        self, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse]:
        self._ensure_open()
        return await self.plugin.pause(timeout=timeout)

    async def subscribe(
        self,
        streams: list[SubscribeTarget],
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        self._ensure_open()
        return await self.plugin.subscribe(
            SubscriberSubscribeRequest(streams=streams), timeout=timeout
        )

    async def unsubscribe(
        self,
        streams: list[UnsubscribeTarget],
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        self._ensure_open()
        return await self.plugin.unsubscribe(
            SubscriberUnsubscribeRequest(streams=streams), timeout=timeout
        )

    async def update(
        self,
        *,
        subscribe: list[SubscribeTarget] | None = None,
        unsubscribe: list[UnsubscribeTarget] | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        self._ensure_open()
        return await self.plugin.update_subscription(
            SubscriberUpdateRequest(subscribe=subscribe, unsubscribe=unsubscribe),
            timeout=timeout,
        )

    async def switch(
        self,
        streams: list[SwitchTarget],
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        self._ensure_open()
        return await self.plugin.switch(
            SubscriberSwitchRequest(streams=streams), timeout=timeout
        )

    async def configure(
        self,
        *,
        streams: list[SubscriberStreamControl] | None = None,
        restart: bool | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        self._ensure_open()
        return await self.plugin.configure_subscriber(
            SubscriberConfigureRequest(streams=streams, restart=restart),
            timeout=timeout,
        )

    async def trickle(self, candidates: Any, *, timeout: float | None = None) -> Any:
        self._ensure_open()
        return await self.plugin.trickle(candidates, timeout=timeout)

    async def complete_trickle(self, *, timeout: float | None = None) -> Any:
        self._ensure_open()
        return await self.plugin.complete_trickle(timeout=timeout)

    async def aclose(self, *, graceful: bool = True) -> None:
        if self._closed:
            return
        self._closed = True
        failures: list[Exception] = []
        if graceful:
            try:
                await self.plugin.leave()
            except Exception as exc:
                failures.append(exc)
        try:
            await self.plugin.detach()
        except Exception as exc:
            failures.append(exc)
        if failures:
            raise ExceptionGroup("failed to close VideoRoom subscriber", failures)


class VideoRoomService:
    """Own related VideoRoom handles for one Janus session lifecycle."""

    def __init__(self, session: Any) -> None:
        if session is None:
            raise TypeError("VideoRoomService requires a Janus session")
        self._session = session
        self._publishers: dict[tuple[JanusId, JanusId], Publisher] = {}
        self._subscribers: dict[tuple[JanusId, JanusId, Hashable], Subscriber] = {}
        self._pending_publishers: dict[
            tuple[JanusId, JanusId], asyncio.Task[Publisher]
        ] = {}
        self._pending_subscribers: dict[
            tuple[JanusId, JanusId, Hashable], asyncio.Task[Subscriber]
        ] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    @property
    def session(self) -> Any:
        return self._session

    @property
    def closed(self) -> bool:
        return self._closed

    def _ensure_open(self) -> None:
        if self._closed:
            raise VideoRoomLifecycleError("VideoRoomService is closed")

    async def __aenter__(self) -> Self:
        self._ensure_open()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.aclose()

    async def _attached_plugin(self) -> VideoRoomPlugin:
        plugin = VideoRoomPlugin(session=self._session)
        await plugin.attach()
        return plugin

    async def _join_publisher_handle(
        self,
        request: PublisherJoinRequest,
        *,
        timeout: float | None,
    ) -> Publisher:
        plugin = await self._attached_plugin()
        try:
            reply = await plugin.join_publisher(request, timeout=timeout)
            if not isinstance(reply.data, VideoRoomJoined):
                raise VideoRoomProtocolError(
                    f"publisher join returned {type(reply.data).__name__}"
                )
            return Publisher(
                plugin=plugin,
                room=reply.data.room,
                participant=reply.data.id,
                private_id=reply.data.private_id,
            )
        except BaseException as exc:
            try:
                await plugin.detach()
            except Exception as cleanup_error:
                exc.add_note(f"publisher detach also failed: {cleanup_error!r}")
            raise

    async def _provision_publisher(
        self,
        key: tuple[JanusId, JanusId],
        request: PublisherJoinRequest,
        *,
        timeout: float | None,
    ) -> Publisher:
        try:
            publisher = await self._join_publisher_handle(request, timeout=timeout)
            async with self._lock:
                if not self._closed:
                    self._publishers[key] = publisher
                    return publisher
            await publisher.aclose(graceful=False)
            raise VideoRoomLifecycleError(
                "VideoRoomService closed while publisher was joining"
            )
        finally:
            async with self._lock:
                if self._pending_publishers.get(key) is asyncio.current_task():
                    self._pending_publishers.pop(key, None)

    async def _join_subscriber_handle(
        self,
        request: SubscriberJoinRequest,
        *,
        owner: JanusId,
        key: Hashable,
        timeout: float | None,
    ) -> Subscriber:
        plugin = await self._attached_plugin()
        try:
            reply = await plugin.join_subscriber(request, timeout=timeout)
            if not isinstance(reply.data, VideoRoomAttached):
                raise VideoRoomProtocolError(
                    f"subscriber join returned {type(reply.data).__name__}"
                )
            return Subscriber(
                plugin=plugin,
                room=reply.data.room,
                owner=owner,
                key=key,
            )
        except BaseException as exc:
            try:
                await plugin.detach()
            except Exception as cleanup_error:
                exc.add_note(f"subscriber detach also failed: {cleanup_error!r}")
            raise

    async def _provision_subscriber(
        self,
        map_key: tuple[JanusId, JanusId, Hashable],
        request: SubscriberJoinRequest,
        *,
        owner: JanusId,
        key: Hashable,
        timeout: float | None,
    ) -> Subscriber:
        try:
            subscriber = await self._join_subscriber_handle(
                request, owner=owner, key=key, timeout=timeout
            )
            async with self._lock:
                if not self._closed:
                    self._subscribers[map_key] = subscriber
                    return subscriber
            await subscriber.aclose(graceful=False)
            raise VideoRoomLifecycleError(
                "VideoRoomService closed while subscriber was joining"
            )
        finally:
            async with self._lock:
                if self._pending_subscribers.get(map_key) is asyncio.current_task():
                    self._pending_subscribers.pop(map_key, None)

    async def create_room(
        self,
        request: VideoRoomCreateRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        """Create a room with a short-lived management handle."""

        self._ensure_open()
        async with VideoRoomPlugin(session=self._session) as plugin:
            return await plugin.create(request, timeout=timeout)

    async def destroy_room(
        self,
        request: VideoRoomDestroyRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        """Destroy a room with a short-lived management handle."""

        self._ensure_open()
        async with VideoRoomPlugin(session=self._session) as plugin:
            return await plugin.destroy(request, timeout=timeout)

    async def publisher(
        self,
        *,
        room: JanusId,
        participant: JanusId,
        display: str | None = None,
        token: str | None = None,
        pin: str | None = None,
        metadata: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Publisher:
        """Get or atomically attach and join one publisher handle."""

        self._ensure_open()
        key = (room, participant)
        async with self._lock:
            self._ensure_open()
            existing = self._publishers.get(key)
            if existing is not None and not existing.closed:
                return existing
            pending = self._pending_publishers.get(key)
            if pending is None:
                pending = asyncio.create_task(
                    self._provision_publisher(
                        key,
                        PublisherJoinRequest(
                            room=room,
                            id=participant,
                            display=display,
                            token=token,
                            pin=pin,
                            metadata=metadata,
                        ),
                        timeout=timeout,
                    ),
                    name=f"videoroom-publisher-{room}-{participant}",
                )
                self._pending_publishers[key] = pending
        return await asyncio.shield(pending)

    async def subscriber(
        self,
        *,
        room: JanusId,
        owner: JanusId,
        key: Hashable,
        streams: list[SubscribeTarget],
        private_id: JanusId | None = None,
        pin: str | None = None,
        use_msid: bool | None = None,
        autoupdate: bool | None = None,
        timeout: float | None = None,
    ) -> Subscriber:
        """Get or atomically attach one named multistream subscription."""

        self._ensure_open()
        map_key = (room, owner, key)
        async with self._lock:
            self._ensure_open()
            existing = self._subscribers.get(map_key)
            if existing is not None and not existing.closed:
                return existing
            pending = self._pending_subscribers.get(map_key)
            if pending is None:
                pending = asyncio.create_task(
                    self._provision_subscriber(
                        map_key,
                        SubscriberJoinRequest(
                            room=room,
                            private_id=private_id,
                            pin=pin,
                            use_msid=use_msid,
                            autoupdate=autoupdate,
                            streams=streams,
                        ),
                        owner=owner,
                        key=key,
                        timeout=timeout,
                    ),
                    name=f"videoroom-subscriber-{room}-{owner}-{key}",
                )
                self._pending_subscribers[map_key] = pending
        return await asyncio.shield(pending)

    async def publish_offer(
        self,
        *,
        room: JanusId,
        participant: JanusId,
        offer: Jsep,
        settings: PublisherPublishRequest | None = None,
        display: str | None = None,
        token: str | None = None,
        pin: str | None = None,
        metadata: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        """Compatibility facade: join once, publish first, configure later."""

        publisher = await self.publisher(
            room=room,
            participant=participant,
            display=display,
            token=token,
            pin=pin,
            metadata=metadata,
            timeout=timeout,
        )
        return await publisher.publish_offer(offer, settings=settings, timeout=timeout)

    async def release_publisher(
        self,
        room: JanusId,
        participant: JanusId,
        *,
        graceful: bool = True,
    ) -> bool:
        async with self._lock:
            key = (room, participant)
            publisher = self._publishers.pop(key, None)
            pending = self._pending_publishers.get(key)
        if pending is not None:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        if publisher is None:
            return pending is not None
        await publisher.aclose(graceful=graceful)
        return True

    async def release_subscriber(
        self,
        room: JanusId,
        owner: JanusId,
        key: Hashable,
        *,
        graceful: bool = True,
    ) -> bool:
        async with self._lock:
            map_key = (room, owner, key)
            subscriber = self._subscribers.pop(map_key, None)
            pending = self._pending_subscribers.get(map_key)
        if pending is not None:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        if subscriber is None:
            return pending is not None
        await subscriber.aclose(graceful=graceful)
        return True

    async def aclose(self, *, graceful: bool = True) -> None:
        """Close every owned handle concurrently; leave the session running."""

        if self._closed:
            return
        self._closed = True
        async with self._lock:
            pending = [
                *self._pending_subscribers.values(),
                *self._pending_publishers.values(),
            ]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        async with self._lock:
            owned = [*self._subscribers.values(), *self._publishers.values()]
            self._subscribers.clear()
            self._publishers.clear()
        results = await asyncio.gather(
            *(item.aclose(graceful=graceful) for item in owned),
            return_exceptions=True,
        )
        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            raise ExceptionGroup("failed to close VideoRoom service handles", failures)
