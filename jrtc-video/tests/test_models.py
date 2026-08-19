from __future__ import annotations

import unittest

from pydantic import ValidationError

from jrtc_video import (
    AddRemotePublisherRequest,
    ListRemotesRequest,
    PublishRemotelyRequest,
    PublisherPublishRequest,
    RemotePublisherStream,
    RemoveRemotePublisherRequest,
    RtpForwardStream,
    SubscribeTarget,
    SubscriberConfigureRequest,
    SubscriberJoinRequest,
    SubscriberStreamControl,
    SubscriberSubscribeRequest,
    SubscriberSwitchRequest,
    SubscriberUnsubscribeRequest,
    SubscriberUpdateRequest,
    SwitchTarget,
    UnpublishRemotelyRequest,
    UnsubscribeTarget,
    UpdateRemotePublisherRequest,
    VideoRoomAllowedRequest,
    VideoRoomCreateRequest,
    VideoRoomEditRequest,
    VideoRoomForwarders,
    VideoRoomJanusError,
    VideoRoomJoiningEvent,
    VideoRoomListForwardersRequest,
    VideoRoomPluginError,
    VideoRoomProtocolError,
    VideoRoomRemotes,
    VideoRoomRtpForwardRequest,
    VideoRoomTalkingEvent,
    parse_videoroom_response,
)


def wire(model: object) -> dict[str, object]:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


class VideoRoomRequestTests(unittest.TestCase):
    def test_numeric_ids_reject_strings_and_booleans(self) -> None:
        for invalid in ("1234", True):
            with self.assertRaises(ValidationError):
                VideoRoomEditRequest(
                    room=invalid, new_description="name"  # type: ignore[arg-type]
                )
            with self.assertRaises(ValidationError):
                SubscribeTarget(feed=invalid)  # type: ignore[arg-type]

    def test_create_and_list_do_not_restate_server_defaults(self) -> None:
        self.assertEqual(wire(VideoRoomCreateRequest()), {"request": "create"})
        self.assertEqual(
            wire(VideoRoomCreateRequest(room=1234, publishers=20)),
            {"request": "create", "room": 1234, "publishers": 20},
        )

    def test_edit_only_accepts_documented_mutable_properties(self) -> None:
        self.assertEqual(
            wire(VideoRoomEditRequest(room=1, new_publishers=12)),
            {"request": "edit", "room": 1, "new_publishers": 12},
        )
        with self.assertRaises(ValidationError):
            VideoRoomEditRequest(room=1, publishers=12)

    def test_acl_tokens_follow_action(self) -> None:
        with self.assertRaises(ValidationError):
            VideoRoomAllowedRequest(room=1, action="add")
        with self.assertRaises(ValidationError):
            VideoRoomAllowedRequest(room=1, action="enable", allowed=["x"])
        self.assertEqual(
            wire(VideoRoomAllowedRequest(room=1, action="add", allowed=["x"])),
            {"request": "allowed", "room": 1, "action": "add", "allowed": ["x"]},
        )

    def test_publish_and_subscriber_defaults_stay_off_wire(self) -> None:
        self.assertEqual(wire(PublisherPublishRequest()), {"request": "publish"})
        join = SubscriberJoinRequest(room=1, streams=[SubscribeTarget(feed=2)])
        self.assertEqual(
            wire(join),
            {
                "request": "join",
                "ptype": "subscriber",
                "room": 1,
                "streams": [{"feed": 2}],
            },
        )
        configure = SubscriberConfigureRequest(
            streams=[SubscriberStreamControl(mid="1")]
        )
        self.assertEqual(
            wire(configure),
            {"request": "configure", "streams": [{"mid": "1"}]},
        )
        self.assertNotIn("restart", wire(configure))

    def test_subscribe_unsubscribe_and_switch_use_distinct_targets(self) -> None:
        subscribe = SubscriberSubscribeRequest(
            streams=[SubscribeTarget(feed=2, mid="video")]
        )
        unsubscribe = SubscriberUnsubscribeRequest(
            streams=[UnsubscribeTarget(sub_mid="1")]
        )
        switch = SubscriberSwitchRequest(
            streams=[SwitchTarget(feed=3, mid="video", sub_mid="1")]
        )
        self.assertEqual(wire(subscribe)["streams"], [{"feed": 2, "mid": "video"}])
        self.assertEqual(wire(unsubscribe)["streams"], [{"sub_mid": "1"}])
        self.assertEqual(
            wire(switch)["streams"],
            [{"feed": 3, "mid": "video", "sub_mid": "1"}],
        )
        with self.assertRaises(ValidationError):
            UnsubscribeTarget(mid="video")
        with self.assertRaises(ValidationError):
            SwitchTarget(feed=3, mid="video")

    def test_update_requires_at_least_one_correct_target_list(self) -> None:
        with self.assertRaises(ValidationError):
            SubscriberUpdateRequest()
        update = SubscriberUpdateRequest(
            subscribe=[SubscribeTarget(feed=2)],
            unsubscribe=[UnsubscribeTarget(feed=3, mid="audio")],
        )
        self.assertEqual(wire(update)["request"], "update")

    def test_rtp_forward_requires_hosts_and_valid_simulcast_mode(self) -> None:
        with self.assertRaises(ValidationError):
            VideoRoomRtpForwardRequest(
                room=1, publisher_id=2, streams=[RtpForwardStream(mid="0", port=5004)]
            )
        request = VideoRoomRtpForwardRequest(
            room=1,
            publisher_id=2,
            host="203.0.113.9",
            streams=[RtpForwardStream(mid="0", port=5004)],
        )
        self.assertEqual(wire(request)["request"], "rtp_forward")
        with self.assertRaises(ValidationError):
            RtpForwardStream(mid="0", port=5004, simulcast=True, port_2=5006)

    def test_listforwarders_uses_wire_spelling(self) -> None:
        self.assertEqual(
            wire(VideoRoomListForwardersRequest(room=1)),
            {"request": "listforwarders", "room": 1},
        )

    def test_all_six_remote_operations_and_profile_aliases(self) -> None:
        stream = RemotePublisherStream(
            type="video", mindex=0, mid="v0", codec="h264", h264_profile="42e01f"
        )
        self.assertEqual(wire(stream)["h264-profile"], "42e01f")
        requests = [
            AddRemotePublisherRequest(room=1, streams=[stream]),
            UpdateRemotePublisherRequest(room=1, id=2, streams=[stream]),
            RemoveRemotePublisherRequest(room=1, id=2),
            PublishRemotelyRequest(
                room=1,
                publisher_id=2,
                remote_id="edge-eu",
                host="198.51.100.8",
                port=5004,
            ),
            UnpublishRemotelyRequest(room=1, publisher_id=2, remote_id="edge-eu"),
            ListRemotesRequest(room=1, publisher_id=2),
        ]
        self.assertEqual(
            [wire(item)["request"] for item in requests],
            [
                "add_remote_publisher",
                "update_remote_publisher",
                "remove_remote_publisher",
                "publish_remotely",
                "unpublish_remotely",
                "list_remotes",
            ],
        )


class VideoRoomResponseTests(unittest.TestCase):
    def test_correct_joining_event_field(self) -> None:
        reply = parse_videoroom_response(
            {
                "videoroom": "event",
                "room": 1,
                "joining": {"id": 2, "display": "Ada", "new_field": True},
            }
        )
        self.assertIsInstance(reply.data, VideoRoomJoiningEvent)
        self.assertEqual(reply.data.joining.id, 2)
        self.assertTrue(reply.data.joining.model_extra["new_field"])

    def test_hyphenated_talking_alias(self) -> None:
        reply = parse_videoroom_response(
            {
                "videoroom": "talking",
                "room": 1,
                "id": 2,
                "audio-level-dBov-avg": 34,
            }
        )
        self.assertIsInstance(reply.data, VideoRoomTalkingEvent)
        self.assertEqual(reply.data.audio_level_dbov_avg, 34)

    def test_forwarders_and_remotes_are_distinct_list_responses(self) -> None:
        forwarders = parse_videoroom_response(
            {
                "videoroom": "forwarders",
                "room": 1,
                "publishers": [
                    {
                        "publisher_id": 2,
                        "forwarders": [
                            {
                                "stream_id": 8,
                                "type": "video",
                                "host": "127.0.0.1",
                                "port": 5004,
                            }
                        ],
                    }
                ],
            }
        )
        self.assertIsInstance(forwarders.data, VideoRoomForwarders)
        remotes = parse_videoroom_response(
            {
                "videoroom": "success",
                "room": 1,
                "id": 2,
                "list": [{"remote_id": "edge", "host": "192.0.2.1", "port": 5004}],
            }
        )
        self.assertIsInstance(remotes.data, VideoRoomRemotes)

    def test_outer_jsep_and_future_fields_are_preserved(self) -> None:
        reply = parse_videoroom_response(
            {
                "janus": "event",
                "transaction": "tx-2",
                "jsep": {"type": "offer", "sdp": "v=0\r\n"},
                "plugindata": {
                    "plugin": "janus.plugin.videoroom",
                    "data": {
                        "videoroom": "attached",
                        "room": 1,
                        "streams": [
                            {
                                "type": "video",
                                "feed_id": 2,
                                "h264-profile": "42e01f",
                                "playout-delay": {"min_delay": 0},
                                "future": "kept",
                            }
                        ],
                    },
                },
            }
        )
        self.assertEqual(reply.jsep.type, "offer")
        self.assertEqual(reply.data.streams[0].h264_profile, "42e01f")
        self.assertEqual(reply.data.streams[0].model_extra["future"], "kept")

    def test_typed_errors(self) -> None:
        with self.assertRaises(VideoRoomJanusError):
            parse_videoroom_response(
                {"janus": "error", "error": {"code": 403, "reason": "denied"}}
            )
        with self.assertRaises(VideoRoomPluginError):
            parse_videoroom_response(
                {"videoroom": "event", "error_code": 426, "error": "no room"}
            )
        with self.assertRaises(VideoRoomProtocolError):
            parse_videoroom_response(
                {
                    "janus": "event",
                    "plugindata": {"plugin": "janus.plugin.sip", "data": {}},
                }
            )


if __name__ == "__main__":
    unittest.main()
