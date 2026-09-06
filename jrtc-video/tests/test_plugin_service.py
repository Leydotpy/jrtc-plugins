from __future__ import annotations

import asyncio
import unittest

from jrtc.core.exceptions import JanusConnectionClosed
from jrtc.models.base import Jsep
from jrtc.models.request import TrickleCandidate

from jrtc_video import (
    PublisherPublishRequest,
    SubscriberJoinRequest,
    SubscribeTarget,
    VideoRoomCreateRequest,
    VideoRoomKickRequest,
    VideoRoomPlugin,
    VideoRoomPluginError,
    VideoRoomProtocolError,
    VideoRoomService,
)


class FakeRegistry:
    def __init__(self) -> None:
        self.handles = {}

    def register(self, handle_id, plugin) -> None:
        self.handles[handle_id] = plugin

    def get(self, handle_id):
        return self.handles.get(handle_id)

    def unregister(self, handle_id) -> None:
        self.handles.pop(handle_id, None)


class FakeSession:
    id = 700

    def __init__(self) -> None:
        self.ready = True
        self.generation = 1
        self.plugins = FakeRegistry()
        self.messages = []
        self.send_options = []
        self.detached = []
        self._next_handle = 10
        self.attach_started = asyncio.Event()
        self.attach_release: asyncio.Event | None = None
        self.send_started = asyncio.Event()
        self.send_release: asyncio.Event | None = None
        self.next_failure: BaseException | None = None
        self.detach_failure: Exception | None = None

    async def attach(self, name: str, *, opaque_id=None):
        self.attach_started.set()
        if self.attach_release is not None:
            await self.attach_release.wait()
        self._next_handle += 1
        return self._next_handle

    async def detach(self, handle_id):
        self.detached.append(handle_id)
        if self.detach_failure is not None:
            raise self.detach_failure
        return {"janus": "success"}

    async def send(self, message, **options: object):
        self.messages.append(message)
        self.send_options.append(options)
        self.send_started.set()
        if self.send_release is not None:
            await self.send_release.wait()
        if self.next_failure is not None:
            failure, self.next_failure = self.next_failure, None
            if isinstance(failure, JanusConnectionClosed):
                self.ready = False
            raise failure
        if message.janus == "trickle":
            return {"janus": "ack", "transaction": message.transaction}
        body = message.body
        request = body["request"]
        room = body.get("room", 1234)
        if request == "join" and body.get("ptype") == "publisher":
            data = {
                "videoroom": "joined",
                "room": room,
                "id": body.get("id", 99),
                "private_id": 9001,
            }
        elif request == "join" and body.get("ptype") == "subscriber":
            data = {
                "videoroom": "attached",
                "room": room,
                "streams": [{"type": "video", "feed_id": body["streams"][0]["feed"]}],
            }
        elif request in {"publish", "configure"}:
            data = {"videoroom": "event", "configured": "ok"}
        elif request == "start":
            data = {"videoroom": "event", "started": "ok", "room": room}
        elif request == "pause":
            data = {"videoroom": "event", "paused": "ok", "room": room}
        elif request == "switch":
            data = {
                "videoroom": "event",
                "switched": "ok",
                "room": room,
                "changes": len(body["streams"]),
            }
        elif request in {"subscribe", "unsubscribe", "update"}:
            data = {"videoroom": "updated", "room": room}
        elif request == "unpublish":
            data = {"videoroom": "event", "unpublished": "ok"}
        elif request == "leave":
            data = {"videoroom": "event", "leaving": "ok"}
        else:
            data = {"videoroom": "success", "room": room}
        return {
            "janus": "event",
            "transaction": message.transaction,
            "jsep": (
                {"type": "answer", "sdp": "v=0\r\n"}
                if request in {"publish", "configure"} and message.jsep is not None
                else None
            ),
            "plugindata": {"plugin": "janus.plugin.videoroom", "data": data},
        }


class VideoRoomPluginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.session = FakeSession()
        self.plugin = VideoRoomPlugin(session=self.session, plugin_id=11)

    async def test_publisher_requires_offer_and_subscriber_start_requires_answer(
        self,
    ) -> None:
        with self.assertRaises(VideoRoomProtocolError):
            await self.plugin.publish(Jsep(type="answer", sdp="v=0\r\n"))
        with self.assertRaises(VideoRoomProtocolError):
            await self.plugin.start(answer=Jsep(type="offer", sdp="v=0\r\n"))

        await self.plugin.publish(Jsep(type="offer", sdp="v=0\r\n"))
        self.assertEqual(self.session.messages[-1].body, {"request": "publish"})
        await self.plugin.start(answer=Jsep(type="answer", sdp="v=0\r\n"))
        self.assertEqual(self.session.messages[-1].body, {"request": "start"})

    async def test_subscriber_join_does_not_send_janus_defaults(self) -> None:
        await self.plugin.join_subscriber(
            SubscriberJoinRequest(room=1, streams=[SubscribeTarget(feed=2)])
        )
        body = self.session.messages[-1].body
        self.assertNotIn("use_msid", body)
        self.assertNotIn("autoupdate", body)

    async def test_ice_sequence_stays_one_ordered_non_waiting_request(self) -> None:
        candidates = [
            TrickleCandidate(
                candidate=f"candidate:{index}",
                sdpMid="0",
                sdpMLineIndex=index,
            )
            for index in range(16)
        ]

        await self.plugin.trickle(candidates)

        request = self.session.messages[-1]
        self.assertIsNone(request.candidate)
        self.assertEqual(request.candidates, candidates)
        self.assertFalse(self.session.send_options[-1]["wait_for_event"])

        await self.plugin.complete_trickle()
        completion = self.session.messages[-1]
        self.assertTrue(completion.candidate.completed)
        self.assertIsNone(completion.candidates)
        self.assertFalse(self.session.send_options[-1]["wait_for_event"])


class VideoRoomServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_management_commands_reuse_one_handle_and_close_once(self) -> None:
        session = FakeSession()
        service = VideoRoomService(session)

        await service.create_room(VideoRoomCreateRequest(room=1234))
        for _ in range(99):
            await service.list_participants(1234)

        metrics = service.metrics
        self.assertEqual(session._next_handle, 11)
        self.assertEqual(metrics.management_attaches, 1)
        self.assertEqual(metrics.management_reuses, 99)
        self.assertEqual(metrics.management_commands, 100)
        self.assertEqual(len(session.detached), 0)

        await asyncio.gather(service.aclose(), service.aclose())
        await service.aclose()
        self.assertEqual(session.detached, [11])
        self.assertEqual(service.metrics.management_detach_attempts, 1)

    async def test_concurrent_first_management_use_attaches_exactly_once(self) -> None:
        session = FakeSession()
        session.attach_release = asyncio.Event()
        service = VideoRoomService(session)

        commands = [asyncio.create_task(service.list_participants(1234)) for _ in range(8)]
        await session.attach_started.wait()
        session.attach_release.set()
        replies = await asyncio.gather(*commands)

        self.assertEqual(len(replies), 8)
        self.assertEqual(session._next_handle, 11)
        self.assertEqual(service.metrics.management_attaches, 1)
        self.assertEqual(service.metrics.management_reuses, 7)
        await service.aclose()

    async def test_close_waits_for_in_flight_management_command(self) -> None:
        session = FakeSession()
        session.send_release = asyncio.Event()
        service = VideoRoomService(session)
        command = asyncio.create_task(service.list_participants(1234))
        await session.send_started.wait()

        close = asyncio.create_task(service.aclose())
        await asyncio.sleep(0)
        self.assertTrue(service.closing)
        self.assertFalse(close.done())

        session.send_release.set()
        await command
        await close
        self.assertEqual(session.detached, [11])

    async def test_session_generation_change_invalidates_without_stale_detach(
        self,
    ) -> None:
        session = FakeSession()
        service = VideoRoomService(session)
        await service.list_participants(1234)

        session.generation = 2
        await service.list_participants(1234)

        self.assertEqual(session._next_handle, 12)
        self.assertEqual(service.metrics.management_invalidations, 1)
        self.assertNotIn(11, session.detached)
        await service.aclose()
        self.assertEqual(session.detached, [12])

    async def test_domain_error_reuses_handle_but_transport_loss_invalidates(
        self,
    ) -> None:
        session = FakeSession()
        service = VideoRoomService(session)
        await service.list_participants(1234)

        session.next_failure = VideoRoomPluginError(426, "room not found")
        with self.assertRaises(VideoRoomPluginError):
            await service.list_participants(9876)
        await service.list_participants(1234)
        self.assertEqual(session._next_handle, 11)
        self.assertEqual(service.metrics.management_domain_failures, 1)

        session.next_failure = JanusConnectionClosed("transport lost")
        with self.assertRaises(JanusConnectionClosed):
            await service.list_participants(1234)
        self.assertEqual(service.metrics.management_lifecycle_failures, 1)
        self.assertEqual(service.metrics.management_invalidations, 1)

        session.ready = True
        session.generation = 2
        await service.list_participants(1234)
        self.assertEqual(session._next_handle, 12)
        await service.aclose()

    async def test_management_and_participant_handles_remain_separate(self) -> None:
        session = FakeSession()
        service = VideoRoomService(session)
        await service.list_participants(1234)
        publisher = await service.publisher(room=1234, participant=7)

        self.assertEqual(session._next_handle, 12)
        self.assertNotEqual(publisher.plugin.id, 11)
        with self.assertRaises(VideoRoomProtocolError):
            await service.management_command("publish")
        await service.kick(VideoRoomKickRequest(room=1234, id=7))
        self.assertEqual(service.metrics.management_attaches, 1)
        await service.aclose(graceful=False)

    async def test_management_detach_failure_is_observable_not_retried(self) -> None:
        session = FakeSession()
        service = VideoRoomService(session)
        await service.create_room(VideoRoomCreateRequest(room=1234))
        session.detach_failure = RuntimeError("detach failed")

        await service.aclose()

        create_requests = [
            message
            for message in session.messages
            if getattr(message, "body", {}).get("request") == "create"
        ]
        self.assertEqual(len(create_requests), 1)
        self.assertEqual(session.detached, [11])
        self.assertEqual(service.metrics.management_detach_failures, 1)

    async def test_concurrent_same_key_joins_are_coalesced(self) -> None:
        session = FakeSession()
        service = VideoRoomService(session)
        first, second = await asyncio.gather(
            service.publisher(room=1234, participant=7),
            service.publisher(room=1234, participant=7),
        )
        self.assertIs(first, second)
        joins = [
            message
            for message in session.messages
            if message.body.get("request") == "join" and message.body.get("ptype") == "publisher"
        ]
        self.assertEqual(len(joins), 1)
        await service.aclose(graceful=False)

    async def test_handles_are_scoped_reused_and_closed(self) -> None:
        session = FakeSession()
        service = VideoRoomService(session)
        publisher = await service.publisher(room=1234, participant=7, display="Ada")
        same = await service.publisher(room=1234, participant=7)
        self.assertIs(publisher, same)

        offer = Jsep(type="offer", sdp="v=0\r\n")
        await publisher.publish_offer(offer, settings=PublisherPublishRequest(record=True))
        await publisher.publish_offer(offer, settings=PublisherPublishRequest(bitrate=256000))
        role_requests = [
            message.body["request"]
            for message in session.messages
            if message.body["request"] in {"publish", "configure"}
        ]
        self.assertEqual(role_requests, ["publish", "configure"])
        self.assertNotIn("record", session.messages[-1].body)

        subscriber = await service.subscriber(
            room=1234,
            owner=7,
            key="stage",
            private_id=publisher.private_id,
            streams=[SubscribeTarget(feed=42, mid="v0")],
        )
        await subscriber.start(answer=Jsep(type="answer", sdp="v=0\r\n"))
        await service.aclose(graceful=False)
        self.assertTrue(service.closed)
        self.assertEqual(len(session.detached), 2)

    async def test_service_does_not_own_or_close_session(self) -> None:
        session = FakeSession()
        async with VideoRoomService(session):
            pass
        self.assertFalse(hasattr(session, "closed"))


if __name__ == "__main__":
    unittest.main()
