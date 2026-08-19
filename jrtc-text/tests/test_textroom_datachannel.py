from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from jrtc_text import (
    ChatMessageRequest,
    JoinRequest,
    MessageEvent,
    SuccessResponse,
    TextRoomBackpressureError,
    TextRoomChannelClosed,
    TextRoomChannelNotOpen,
    TextRoomDataChannel,
    TextRoomPluginError,
    TextRoomProtocolError,
    TextRoomTransactionTimeout,
)


class FakeChannel:
    def __init__(self, *, ready_state: str = "open", asynchronous: bool = False) -> None:
        self.ready_state = ready_state
        self.asynchronous = asynchronous
        self.sent: list[str] = []

    def send(self, data: str) -> Any:
        self.sent.append(data)
        if not self.asynchronous:
            return None

        async def complete() -> None:
            await asyncio.sleep(0)

        return complete()


def test_transaction_success_plugin_error_timeout_and_async_send() -> None:
    async def scenario() -> None:
        channel = FakeChannel(asynchronous=True)
        manager = TextRoomDataChannel(channel, default_timeout=0.05)

        success_task = asyncio.create_task(
            manager.request(JoinRequest(room=10, username="alice", transaction="join-ok"))
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert json.loads(channel.sent[-1]) == {
            "textroom": "join",
            "transaction": "join-ok",
            "room": 10,
            "username": "alice",
        }
        manager.feed_data('{"textroom":"success","transaction":"join-ok","participants":[]}')
        success = await success_task
        assert isinstance(success, SuccessResponse)
        assert manager.pending_count == 0

        error_task = asyncio.create_task(
            manager.request(JoinRequest(room=10, username="bob", transaction="join-error"))
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        manager.feed_data(
            '{"textroom":"error","transaction":"join-error",'
            '"error_code":420,"error":"Username exists"}'
        )
        with pytest.raises(TextRoomPluginError) as error:
            await error_task
        assert error.value.code == 420

        with pytest.raises(TextRoomTransactionTimeout) as timeout:
            await manager.request(
                JoinRequest(room=10, username="carol", transaction="join-timeout"),
                timeout=0.001,
            )
        assert timeout.value.transaction == "join-timeout"
        assert manager.pending_count == 0

    asyncio.run(scenario())


def test_backpressure_cancellation_and_ack_free_messages_are_bounded() -> None:
    async def scenario() -> None:
        channel = FakeChannel()
        manager = TextRoomDataChannel(channel, max_pending=1)
        pending = asyncio.create_task(
            manager.request(JoinRequest(room=10, username="alice", transaction="pending"))
        )
        await asyncio.sleep(0)
        with pytest.raises(TextRoomBackpressureError):
            await manager.request(JoinRequest(room=10, username="bob", transaction="overflow"))
        assert len(channel.sent) == 1

        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert manager.pending_count == 0

        response = await manager.request(
            ChatMessageRequest(
                room=10,
                text="fire and forget",
                ack=False,
                transaction="no-ack",
            )
        )
        assert response is None
        assert manager.pending_count == 0
        assert json.loads(channel.sent[-1])["ack"] is False

    asyncio.run(scenario())


def test_unsolicited_event_queue_drops_oldest_and_counts_late_responses() -> None:
    async def scenario() -> None:
        manager = TextRoomDataChannel(FakeChannel(), max_events=1)
        manager.feed_data(
            '{"textroom":"message","room":10,"from":"alice","date":"one","text":"first"}'
        )
        manager.feed_data(
            '{"textroom":"message","room":10,"from":"bob","date":"two","text":"second"}'
        )
        assert manager.dropped_events == 1
        event = await manager.next_event(timeout=0.1)
        assert isinstance(event, MessageEvent)
        assert event.from_ == "bob"

        parsed = manager.feed_data('{"textroom":"success","transaction":"already-timed-out"}')
        assert isinstance(parsed, SuccessResponse)
        assert manager.late_responses == 1

    asyncio.run(scenario())


def test_close_and_malformed_correlated_payloads_fail_pending_futures() -> None:
    async def scenario() -> None:
        manager = TextRoomDataChannel(FakeChannel())
        malformed = asyncio.create_task(
            manager.request(JoinRequest(room=10, username="alice", transaction="malformed"))
        )
        await asyncio.sleep(0)
        with pytest.raises(TextRoomProtocolError):
            manager.feed_data('{"textroom":"message","transaction":"malformed","room":10}')
        with pytest.raises(TextRoomProtocolError):
            await malformed
        assert manager.pending_count == 0

        closing = asyncio.create_task(
            manager.request(JoinRequest(room=10, username="bob", transaction="closing"))
        )
        await asyncio.sleep(0)
        await manager.aclose()
        with pytest.raises(TextRoomChannelClosed):
            await closing
        with pytest.raises(TextRoomChannelClosed):
            manager.feed_data('{"textroom":"success"}')

    asyncio.run(scenario())


def test_channel_state_size_and_encoding_guards() -> None:
    async def scenario() -> None:
        closed = TextRoomDataChannel(FakeChannel(ready_state="closed"))
        with pytest.raises(TextRoomChannelNotOpen):
            await closed.request(JoinRequest(room=10, username="alice", transaction="closed"))

        small = TextRoomDataChannel(FakeChannel(), max_message_bytes=32)
        with pytest.raises(TextRoomProtocolError, match="outbound"):
            await small.request(JoinRequest(room=10, username="a" * 100, transaction="oversize"))
        assert small.pending_count == 0

        manager = TextRoomDataChannel(FakeChannel())
        with pytest.raises(TextRoomProtocolError, match="UTF-8"):
            manager.feed_data(b"\xff")
        with pytest.raises(TextRoomProtocolError, match="JSON"):
            manager.feed_data("not-json")
        with pytest.raises(TextRoomProtocolError, match="object"):
            manager.feed_data("[]")

    asyncio.run(scenario())
