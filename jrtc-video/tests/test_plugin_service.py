from __future__ import annotations

import asyncio
import unittest

from jrtc.models.base import Jsep

from jrtc_video import (
    PublisherPublishRequest,
    SubscribeTarget,
    SubscriberJoinRequest,
    VideoRoomPlugin,
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
        self.plugins = FakeRegistry()
        self.messages = []
        self.detached = []
        self._next_handle = 10

    async def attach(self, name: str, *, opaque_id=None):
        self._next_handle += 1
        return self._next_handle

    async def detach(self, handle_id):
        self.detached.append(handle_id)
        return {"janus": "success"}

    async def send(self, message, **_: object):
        self.messages.append(message)
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


class VideoRoomServiceTests(unittest.IsolatedAsyncioTestCase):
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
            if message.body.get("request") == "join"
            and message.body.get("ptype") == "publisher"
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
        await publisher.publish_offer(
            offer, settings=PublisherPublishRequest(record=True)
        )
        await publisher.publish_offer(
            offer, settings=PublisherPublishRequest(bitrate=256000)
        )
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
