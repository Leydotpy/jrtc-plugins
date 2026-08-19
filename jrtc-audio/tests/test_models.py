from __future__ import annotations

import unittest

from pydantic import ValidationError

from jrtc_audio import (
    AudioBridgeAllowedRequest,
    AudioBridgeAnnouncementStarted,
    AudioBridgeAnnouncements,
    AudioBridgeChangeRoomRequest,
    AudioBridgeConfigureRequest,
    AudioBridgeCreateRequest,
    AudioBridgeDestroyRequest,
    AudioBridgeEditRequest,
    AudioBridgeEnableMjrsRequest,
    AudioBridgeEnableRecordingRequest,
    AudioBridgeExistsRequest,
    AudioBridgeForwarders,
    AudioBridgeIsPlayingRequest,
    AudioBridgeJanusError,
    AudioBridgeJoinRequest,
    AudioBridgeKickAllRequest,
    AudioBridgeKickRequest,
    AudioBridgeLeaveRequest,
    AudioBridgeListAnnouncementsRequest,
    AudioBridgeListForwardersRequest,
    AudioBridgeListParticipantsRequest,
    AudioBridgeListRequest,
    AudioBridgeMuteRequest,
    AudioBridgeMuteRoomRequest,
    AudioBridgePlayFileRequest,
    AudioBridgePluginError,
    AudioBridgeProtocolError,
    AudioBridgeResetDecoderRequest,
    AudioBridgeResumeRequest,
    AudioBridgeRtpForwardRequest,
    AudioBridgeRtpTransport,
    AudioBridgeStopAllFilesRequest,
    AudioBridgeStopFileRequest,
    AudioBridgeStopRtpForwardRequest,
    AudioBridgeSuspendRequest,
    AudioBridgeUnmuteRequest,
    AudioBridgeUnmuteRoomRequest,
    parse_audiobridge_response,
)


def wire(model: object) -> dict[str, object]:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


class AudioBridgeRequestTests(unittest.TestCase):
    def test_numeric_ids_reject_strings_and_booleans(self) -> None:
        for invalid in ("1234", True):
            with self.assertRaises(ValidationError):
                AudioBridgeDestroyRequest(room=invalid)  # type: ignore[arg-type]
            with self.assertRaises(ValidationError):
                AudioBridgeKickRequest(room=1, id=invalid)  # type: ignore[arg-type]
            with self.assertRaises(ValidationError):
                AudioBridgeStopRtpForwardRequest(
                    room=1, stream_id=invalid  # type: ignore[arg-type]
                )

    def test_create_keeps_server_defaults_off_wire(self) -> None:
        self.assertEqual(
            wire(AudioBridgeCreateRequest(description="Stand-up")),
            {"request": "create", "description": "Stand-up"},
        )

    def test_recording_and_mjr_commands_are_distinct(self) -> None:
        self.assertEqual(
            wire(AudioBridgeEnableRecordingRequest(room=1234, record=True)),
            {"request": "enable_recording", "room": 1234, "record": True},
        )
        self.assertEqual(
            wire(AudioBridgeEnableMjrsRequest(room=1234, mjrs=True)),
            {"request": "enable_mjrs", "room": 1234, "mjrs": True},
        )

    def test_room_secrets_are_conditionally_optional(self) -> None:
        requests = [
            AudioBridgeEditRequest(room=1),
            AudioBridgeDestroyRequest(room=1),
            AudioBridgeAllowedRequest(room=1, action="enable"),
            AudioBridgeKickRequest(room=1, id=2),
            AudioBridgeKickAllRequest(room=1),
            AudioBridgeSuspendRequest(room=1, id=2),
            AudioBridgeResumeRequest(room=1, id=2),
            AudioBridgeMuteRequest(room=1, id=2),
            AudioBridgeUnmuteRequest(room=1, id=2),
            AudioBridgeMuteRoomRequest(room=1),
            AudioBridgeUnmuteRoomRequest(room=1),
            AudioBridgePlayFileRequest(room=1, filename="notice.opus"),
            AudioBridgeIsPlayingRequest(room=1, file_id="notice"),
            AudioBridgeListAnnouncementsRequest(room=1),
            AudioBridgeStopFileRequest(room=1, file_id="notice"),
            AudioBridgeStopAllFilesRequest(room=1),
        ]
        self.assertTrue(all("secret" not in wire(request) for request in requests))

    def test_acl_tokens_follow_action(self) -> None:
        with self.assertRaises(ValidationError):
            AudioBridgeAllowedRequest(room=1, action="add")
        with self.assertRaises(ValidationError):
            AudioBridgeAllowedRequest(room=1, action="disable", allowed=["a"])
        self.assertEqual(
            wire(AudioBridgeAllowedRequest(room=1, action="remove", allowed=["a"])),
            {"request": "allowed", "room": 1, "action": "remove", "allowed": ["a"]},
        )

    def test_plain_rtp_empty_and_complete_shapes(self) -> None:
        self.assertEqual(wire(AudioBridgeRtpTransport()), {})
        self.assertEqual(
            wire(AudioBridgeRtpTransport(ip="203.0.113.8", port=5004)),
            {"ip": "203.0.113.8", "port": 5004},
        )
        with self.assertRaises(ValidationError):
            AudioBridgeRtpTransport(ip="203.0.113.8")

    def test_join_and_configure_support_reversed_plain_rtp(self) -> None:
        join = AudioBridgeJoinRequest(
            room=1234, generate_offer=True, rtp=AudioBridgeRtpTransport()
        )
        self.assertEqual(
            wire(join),
            {"request": "join", "room": 1234, "generate_offer": True, "rtp": {}},
        )
        configure = AudioBridgeConfigureRequest(
            rtp=AudioBridgeRtpTransport(ip="198.51.100.4", port=6000)
        )
        self.assertEqual(
            wire(configure),
            {"request": "configure", "rtp": {"ip": "198.51.100.4", "port": 6000}},
        )

    def test_documented_numeric_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            AudioBridgeJoinRequest(room=1, quality=11)
        with self.assertRaises(ValidationError):
            AudioBridgeJoinRequest(room=1, expected_loss=21)
        with self.assertRaises(ValidationError):
            AudioBridgeConfigureRequest(spatial_position=101)

    def test_all_documented_commands_have_exact_discriminators(self) -> None:
        requests = [
            AudioBridgeCreateRequest(),
            AudioBridgeEditRequest(room=1),
            AudioBridgeDestroyRequest(room=1),
            AudioBridgeEnableRecordingRequest(room=1, record=False),
            AudioBridgeEnableMjrsRequest(room=1, mjrs=False),
            AudioBridgeExistsRequest(room=1),
            AudioBridgeAllowedRequest(room=1, action="enable"),
            AudioBridgeKickRequest(room=1, id=2),
            AudioBridgeKickAllRequest(room=1),
            AudioBridgeSuspendRequest(room=1, id=2),
            AudioBridgeResumeRequest(room=1, id=2),
            AudioBridgeListRequest(),
            AudioBridgeListParticipantsRequest(room=1),
            AudioBridgeResetDecoderRequest(),
            AudioBridgeMuteRequest(room=1, id=2),
            AudioBridgeUnmuteRequest(room=1, id=2),
            AudioBridgeMuteRoomRequest(room=1),
            AudioBridgeUnmuteRoomRequest(room=1),
            AudioBridgeRtpForwardRequest(room=1, host="127.0.0.1", port=5004),
            AudioBridgeStopRtpForwardRequest(room=1, stream_id=3),
            AudioBridgeListForwardersRequest(room=1),
            AudioBridgePlayFileRequest(room=1, filename="a.opus"),
            AudioBridgeIsPlayingRequest(room=1, file_id="a"),
            AudioBridgeListAnnouncementsRequest(room=1),
            AudioBridgeStopFileRequest(room=1, file_id="a"),
            AudioBridgeStopAllFilesRequest(room=1),
            AudioBridgeJoinRequest(room=1),
            AudioBridgeConfigureRequest(),
            AudioBridgeLeaveRequest(),
            AudioBridgeChangeRoomRequest(room=2),
        ]
        expected = [
            "create",
            "edit",
            "destroy",
            "enable_recording",
            "enable_mjrs",
            "exists",
            "allowed",
            "kick",
            "kick_all",
            "suspend",
            "resume",
            "list",
            "listparticipants",
            "resetdecoder",
            "mute",
            "unmute",
            "mute_room",
            "unmute_room",
            "rtp_forward",
            "stop_rtp_forward",
            "listforwarders",
            "play_file",
            "is_playing",
            "listannouncements",
            "stop_file",
            "stop_all_files",
            "join",
            "configure",
            "leave",
            "changeroom",
        ]
        self.assertEqual([wire(item)["request"] for item in requests], expected)


class AudioBridgeResponseTests(unittest.TestCase):
    def test_outer_event_parses_jsep_and_retains_future_fields(self) -> None:
        reply = parse_audiobridge_response(
            {
                "janus": "event",
                "transaction": "tx-1",
                "jsep": {"type": "answer", "sdp": "v=0\r\n", "future": True},
                "plugindata": {
                    "plugin": "janus.plugin.audiobridge",
                    "data": {
                        "audiobridge": "event",
                        "room": 1234,
                        "result": "ok",
                        "server_extension": 7,
                    },
                },
            }
        )
        self.assertEqual(reply.transaction, "tx-1")
        self.assertEqual(reply.jsep.type, "answer")
        self.assertEqual(reply.data.model_extra["server_extension"], 7)

    def test_forwarder_announcement_and_event_variants(self) -> None:
        forwarders = parse_audiobridge_response(
            {
                "audiobridge": "forwarders",
                "room": 1,
                "rtp_forwarders": [{"stream_id": 9, "ip": "127.0.0.1", "port": 5004}],
            }
        )
        self.assertIsInstance(forwarders.data, AudioBridgeForwarders)
        announcements = parse_audiobridge_response(
            {
                "audiobridge": "announcements",
                "room": 1,
                "announcements": [
                    {"file_id": "intro", "filename": "intro.opus", "playing": True}
                ],
            }
        )
        self.assertIsInstance(announcements.data, AudioBridgeAnnouncements)
        started = parse_audiobridge_response(
            {"audiobridge": "announcement-started", "room": 1, "file_id": "intro"}
        )
        self.assertIsInstance(started.data, AudioBridgeAnnouncementStarted)

    def test_typed_outer_plugin_and_protocol_errors(self) -> None:
        with self.assertRaises(AudioBridgeJanusError):
            parse_audiobridge_response(
                {"janus": "error", "error": {"code": 403, "reason": "denied"}}
            )
        with self.assertRaises(AudioBridgePluginError):
            parse_audiobridge_response(
                {"audiobridge": "event", "error_code": 486, "error": "no room"}
            )
        with self.assertRaises(AudioBridgeProtocolError):
            parse_audiobridge_response(
                {
                    "janus": "event",
                    "plugindata": {"plugin": "janus.plugin.videoroom", "data": {}},
                }
            )


if __name__ == "__main__":
    unittest.main()
