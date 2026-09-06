"""Lifecycle-managed VideoRoom publisher and subscriber orchestration.

This module intentionally has no process-global state and no synchronous loop
runner. Every object lives on the caller's current asyncio loop and the service
owns only the plugin handles it creates, never the Janus session itself.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Hashable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Self, TypeVar

from jrtc.core.exceptions import JanusTransportError
from jrtc.models.base import Jsep
from jrtc.models.common import JanusId
from jrtc.models.request import TrickleCandidate

from .errors import (
    VideoRoomError,
    VideoRoomJanusError,
    VideoRoomLifecycleError,
    VideoRoomProtocolError,
)
from .models import (
    AddRemotePublisherRequest,
    ListRemotesRequest,
    PublisherConfigureRequest,
    PublisherJoinRequest,
    PublisherPublishRequest,
    PublishRemotelyRequest,
    RemoveRemotePublisherRequest,
    SubscriberConfigureRequest,
    SubscriberJoinRequest,
    SubscriberStreamControl,
    SubscriberSubscribeRequest,
    SubscriberSwitchRequest,
    SubscriberUnsubscribeRequest,
    SubscriberUpdateRequest,
    SubscribeTarget,
    SwitchTarget,
    UnpublishRemotelyRequest,
    UnsubscribeTarget,
    UpdateRemotePublisherRequest,
    VideoRoomAllowedRequest,
    VideoRoomAttached,
    VideoRoomCreateRequest,
    VideoRoomDestroyRequest,
    VideoRoomEditRequest,
    VideoRoomEnableRecordingRequest,
    VideoRoomJoined,
    VideoRoomKickRequest,
    VideoRoomListForwardersRequest,
    VideoRoomModerateRequest,
    VideoRoomReply,
    VideoRoomResponse,
    VideoRoomRtpForwardRequest,
    VideoRoomStopRtpForwardRequest,
)
from .plugin import VideoRoomPlugin

_T = TypeVar("_T")

_MANAGEMENT_METHODS = frozenset(
    {
        "add_remote_publisher",
        "allowed",
        "create",
        "destroy",
        "edit",
        "enable_recording",
        "exists",
        "kick",
        "list_forwarders",
        "list_participants",
        "list_remotes",
        "list_rooms",
        "moderate",
        "publish_remotely",
        "remove_remote_publisher",
        "rtp_forward",
        "stop_rtp_forward",
        "unpublish_remotely",
        "update_remote_publisher",
    }
)

# Janus' public API error codes for an unknown session/handle.  These are
# lifecycle failures, unlike VideoRoom domain errors such as an unknown room.
_LOST_RESOURCE_CODES = frozenset({458, 459})


@dataclass(frozen=True, slots=True)
class VideoRoomServiceMetrics:
    """Low-overhead snapshot of management-handle lifecycle activity."""

    management_attaches: int
    management_reuses: int
    management_invalidations: int
    management_detach_attempts: int
    management_detach_failures: int
    management_commands: int
    management_command_failures: int
    management_lifecycle_failures: int
    management_domain_failures: int
    management_command_seconds_total: float
    management_command_seconds_max: float


@dataclass(slots=True)
class _MutableServiceMetrics:
    management_attaches: int = 0
    management_reuses: int = 0
    management_invalidations: int = 0
    management_detach_attempts: int = 0
    management_detach_failures: int = 0
    management_commands: int = 0
    management_command_failures: int = 0
    management_lifecycle_failures: int = 0
    management_domain_failures: int = 0
    management_command_seconds_total: float = 0.0
    management_command_seconds_max: float = 0.0

    def snapshot(self) -> VideoRoomServiceMetrics:
        return VideoRoomServiceMetrics(
            management_attaches=self.management_attaches,
            management_reuses=self.management_reuses,
            management_invalidations=self.management_invalidations,
            management_detach_attempts=self.management_detach_attempts,
            management_detach_failures=self.management_detach_failures,
            management_commands=self.management_commands,
            management_command_failures=self.management_command_failures,
            management_lifecycle_failures=self.management_lifecycle_failures,
            management_domain_failures=self.management_domain_failures,
            management_command_seconds_total=self.management_command_seconds_total,
            management_command_seconds_max=self.management_command_seconds_max,
        )


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
        return await self.plugin.configure_publisher(configure, offer=offer, timeout=timeout)

    async def configure(
        self,
        settings: PublisherConfigureRequest,
        *,
        offer: Jsep | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        self._ensure_open()
        return await self.plugin.configure_publisher(settings, offer=offer, timeout=timeout)

    async def unpublish(
        self, *, timeout: float | None = None
    ) -> VideoRoomReply[VideoRoomResponse] | None:
        self._ensure_open()
        if not self._published:
            return None
        reply = await self.plugin.unpublish(timeout=timeout)
        self._published = False
        return reply

    async def trickle(
        self,
        candidates: TrickleCandidate | Sequence[TrickleCandidate],
        *,
        timeout: float | None = None,
    ) -> Any:
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

    async def pause(self, *, timeout: float | None = None) -> VideoRoomReply[VideoRoomResponse]:
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
        return await self.plugin.switch(SubscriberSwitchRequest(streams=streams), timeout=timeout)

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

    async def trickle(
        self,
        candidates: TrickleCandidate | Sequence[TrickleCandidate],
        *,
        timeout: float | None = None,
    ) -> Any:
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
        self._pending_publishers: dict[tuple[JanusId, JanusId], asyncio.Task[Publisher]] = {}
        self._pending_subscribers: dict[
            tuple[JanusId, JanusId, Hashable], asyncio.Task[Subscriber]
        ] = {}
        self._lock = asyncio.Lock()
        self._management_lock = asyncio.Lock()
        self._close_lock = asyncio.Lock()
        self._management_plugin: VideoRoomPlugin | None = None
        self._management_generation: object | None = None
        self._metrics = _MutableServiceMetrics()
        self._closing = False
        self._closed = False

    @property
    def session(self) -> Any:
        return self._session

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def closing(self) -> bool:
        return self._closing and not self._closed

    @property
    def metrics(self) -> VideoRoomServiceMetrics:
        """Return an immutable, internally consistent counter snapshot."""

        return self._metrics.snapshot()

    def _ensure_open(self) -> None:
        if self._closing or self._closed:
            raise VideoRoomLifecycleError("VideoRoomService is closed")

    async def __aenter__(self) -> Self:
        self._ensure_open()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.aclose()

    def _session_generation_value(self) -> object | None:
        return getattr(self._session, "generation", None)

    def _session_is_healthy(self) -> bool:
        return bool(getattr(self._session, "ready", True))

    def _management_plugin_is_usable(
        self,
        plugin: VideoRoomPlugin,
        generation: object | None,
    ) -> bool:
        if plugin.session is not self._session or not self._session_is_healthy():
            return False
        current_generation = self._session_generation_value()
        if generation is not None and current_generation != generation:
            return False
        try:
            handle_id = plugin.id
        except RuntimeError:
            return False
        registry = getattr(self._session, "plugins", None)
        if registry is not None:
            try:
                if registry.get(handle_id) is not plugin:
                    return False
            except (AttributeError, KeyError):
                return False
        return True

    async def _dispose_management_plugin(
        self,
        plugin: VideoRoomPlugin,
        *,
        detach: bool,
    ) -> None:
        """Release one cached handle without surfacing best-effort cleanup errors."""

        try:
            if detach:
                self._metrics.management_detach_attempts += 1
                await plugin.detach()
            else:
                await plugin.aclose()
        except Exception:
            self._metrics.management_detach_failures += 1
            with suppress(Exception):
                await plugin.aclose()

    def _can_detach_management_plugin(
        self,
        plugin: VideoRoomPlugin,
        generation: object | None,
    ) -> bool:
        """Avoid sending a stale handle ID on a different session generation."""

        return self._management_plugin_is_usable(plugin, generation)

    async def _invalidate_management_plugin_locked(
        self,
        plugin: VideoRoomPlugin,
    ) -> bool:
        if self._management_plugin is not plugin:
            return False
        generation = self._management_generation
        self._management_plugin = None
        self._management_generation = None
        self._metrics.management_invalidations += 1
        await self._dispose_management_plugin(
            plugin,
            detach=self._can_detach_management_plugin(plugin, generation),
        )
        return True

    async def invalidate_management_plugin(self) -> bool:
        """Fence the cached control handle after a session/handle loss signal."""

        async with self._management_lock:
            plugin = self._management_plugin
            if plugin is None:
                return False
            return await self._invalidate_management_plugin_locked(plugin)

    async def _get_management_plugin_locked(self) -> VideoRoomPlugin:
        self._ensure_open()
        cached = self._management_plugin
        if cached is not None and self._management_plugin_is_usable(
            cached, self._management_generation
        ):
            self._metrics.management_reuses += 1
            return cached
        if cached is not None:
            await self._invalidate_management_plugin_locked(cached)

        if not self._session_is_healthy():
            raise VideoRoomLifecycleError(
                "cannot attach a management handle to an inactive Janus session"
            )

        plugin = VideoRoomPlugin(session=self._session)
        try:
            await plugin.attach()
        except BaseException:
            await plugin.aclose()
            raise

        generation = self._session_generation_value()
        if self._closing or self._closed:
            await self._dispose_management_plugin(plugin, detach=True)
            raise VideoRoomLifecycleError(
                "VideoRoomService closed while attaching its management handle"
            )
        if not self._management_plugin_is_usable(plugin, generation):
            await self._dispose_management_plugin(plugin, detach=False)
            raise VideoRoomLifecycleError(
                "Janus session was lost while attaching its management handle"
            )

        self._management_plugin = plugin
        self._management_generation = generation
        self._metrics.management_attaches += 1
        return plugin

    async def _get_management_plugin(self) -> VideoRoomPlugin:
        """Return the one healthy lazily attached control handle for this service."""

        async with self._management_lock:
            return await self._get_management_plugin_locked()

    def _failure_invalidates_management_plugin(
        self,
        exc: BaseException,
        plugin: VideoRoomPlugin | None,
    ) -> bool:
        if plugin is not None and not self._management_plugin_is_usable(
            plugin, self._management_generation
        ):
            return True
        if isinstance(exc, JanusTransportError):
            return True
        if isinstance(exc, VideoRoomLifecycleError):
            return True
        return isinstance(exc, VideoRoomJanusError) and exc.code in _LOST_RESOURCE_CODES

    async def _run_management_command(
        self,
        command_name: str,
        operation: Callable[[VideoRoomPlugin], Awaitable[_T]],
    ) -> _T:
        started = time.monotonic()
        self._metrics.management_commands += 1
        try:
            async with self._management_lock:
                plugin: VideoRoomPlugin | None = None
                try:
                    plugin = await self._get_management_plugin_locked()
                    return await operation(plugin)
                except BaseException as exc:
                    self._metrics.management_command_failures += 1
                    lifecycle_failure = self._failure_invalidates_management_plugin(exc, plugin)
                    if lifecycle_failure:
                        self._metrics.management_lifecycle_failures += 1
                        if plugin is not None:
                            await self._invalidate_management_plugin_locked(plugin)
                    elif isinstance(exc, VideoRoomError):
                        self._metrics.management_domain_failures += 1
                    raise
        finally:
            duration = time.monotonic() - started
            self._metrics.management_command_seconds_total += duration
            self._metrics.management_command_seconds_max = max(
                self._metrics.management_command_seconds_max,
                duration,
            )

    async def management_command(
        self,
        method_name: str,
        *,
        args: Sequence[Any] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """Invoke a whitelisted control command on the reusable management handle."""

        if method_name not in _MANAGEMENT_METHODS:
            raise VideoRoomProtocolError(f"{method_name!r} is not a VideoRoom management command")
        call_args = tuple(args)
        call_kwargs = dict(kwargs or {})

        async def operation(plugin: VideoRoomPlugin) -> Any:
            method = getattr(plugin, method_name)
            return await method(*call_args, **call_kwargs)

        return await self._run_management_command(method_name, operation)

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
                raise VideoRoomProtocolError(f"publisher join returned {type(reply.data).__name__}")
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
            raise VideoRoomLifecycleError("VideoRoomService closed while publisher was joining")
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
            raise VideoRoomLifecycleError("VideoRoomService closed while subscriber was joining")
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
        return await self._run_management_command(
            "create",
            lambda plugin: plugin.create(request, timeout=timeout),
        )

    async def destroy_room(
        self,
        request: VideoRoomDestroyRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "destroy",
            lambda plugin: plugin.destroy(request, timeout=timeout),
        )

    async def edit_room(
        self,
        request: VideoRoomEditRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "edit", lambda plugin: plugin.edit(request, timeout=timeout)
        )

    async def room_exists(
        self,
        room: JanusId,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "exists", lambda plugin: plugin.exists(room, timeout=timeout)
        )

    async def allowed(
        self,
        request: VideoRoomAllowedRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "allowed", lambda plugin: plugin.allowed(request, timeout=timeout)
        )

    async def kick(
        self,
        request: VideoRoomKickRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "kick", lambda plugin: plugin.kick(request, timeout=timeout)
        )

    async def moderate(
        self,
        request: VideoRoomModerateRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "moderate", lambda plugin: plugin.moderate(request, timeout=timeout)
        )

    async def enable_recording(
        self,
        request: VideoRoomEnableRecordingRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "enable_recording",
            lambda plugin: plugin.enable_recording(request, timeout=timeout),
        )

    async def list_rooms(
        self,
        *,
        admin_key: str | None = None,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "list_rooms",
            lambda plugin: plugin.list_rooms(admin_key=admin_key, timeout=timeout),
        )

    async def list_participants(
        self,
        room: JanusId,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "list_participants",
            lambda plugin: plugin.list_participants(room, timeout=timeout),
        )

    async def rtp_forward(
        self,
        request: VideoRoomRtpForwardRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "rtp_forward", lambda plugin: plugin.rtp_forward(request, timeout=timeout)
        )

    async def stop_rtp_forward(
        self,
        request: VideoRoomStopRtpForwardRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "stop_rtp_forward",
            lambda plugin: plugin.stop_rtp_forward(request, timeout=timeout),
        )

    async def list_forwarders(
        self,
        request: VideoRoomListForwardersRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "list_forwarders",
            lambda plugin: plugin.list_forwarders(request, timeout=timeout),
        )

    async def add_remote_publisher(
        self,
        request: AddRemotePublisherRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "add_remote_publisher",
            lambda plugin: plugin.add_remote_publisher(request, timeout=timeout),
        )

    async def update_remote_publisher(
        self,
        request: UpdateRemotePublisherRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "update_remote_publisher",
            lambda plugin: plugin.update_remote_publisher(request, timeout=timeout),
        )

    async def remove_remote_publisher(
        self,
        request: RemoveRemotePublisherRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "remove_remote_publisher",
            lambda plugin: plugin.remove_remote_publisher(request, timeout=timeout),
        )

    async def publish_remotely(
        self,
        request: PublishRemotelyRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "publish_remotely",
            lambda plugin: plugin.publish_remotely(request, timeout=timeout),
        )

    async def unpublish_remotely(
        self,
        request: UnpublishRemotelyRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "unpublish_remotely",
            lambda plugin: plugin.unpublish_remotely(request, timeout=timeout),
        )

    async def list_remotes(
        self,
        request: ListRemotesRequest,
        *,
        timeout: float | None = None,
    ) -> VideoRoomReply[VideoRoomResponse]:
        return await self._run_management_command(
            "list_remotes",
            lambda plugin: plugin.list_remotes(request, timeout=timeout),
        )

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
        """Close every owned handle deterministically; leave the session running."""

        async with self._close_lock:
            if self._closed:
                return
            self._closing = True
            failures: list[Exception] = []
            try:
                # Management commands hold this lock for their complete
                # invocation.  Close therefore cannot detach a healthy handle
                # from underneath an in-flight command, and queued commands
                # observe ``_closing`` before they can create another handle.
                async with self._management_lock:
                    management_plugin = self._management_plugin
                    management_generation = self._management_generation
                    self._management_plugin = None
                    self._management_generation = None
                    if management_plugin is not None:
                        await self._dispose_management_plugin(
                            management_plugin,
                            detach=self._can_detach_management_plugin(
                                management_plugin, management_generation
                            ),
                        )

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
                failures.extend(result for result in results if isinstance(result, Exception))
            finally:
                self._closed = True
                self._closing = False
            if failures:
                raise ExceptionGroup("failed to close VideoRoom service handles", failures)
