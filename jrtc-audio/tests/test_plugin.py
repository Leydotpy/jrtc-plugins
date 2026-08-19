from __future__ import annotations

import unittest

from jrtc.models.base import Jsep

from jrtc_audio import (
    AudioBridgeConfigureRequest,
    AudioBridgeJoinRequest,
    AudioBridgePlugin,
    AudioBridgeProtocolError,
    AudioBridgeRtpTransport,
)


class FakeSession:
    id = 77

    def __init__(self) -> None:
        self.messages = []

    async def send(self, message, **_: object):
        self.messages.append(message)
        return {
            "janus": "event",
            "transaction": message.transaction,
            "plugindata": {
                "plugin": "janus.plugin.audiobridge",
                "data": {"audiobridge": "success"},
            },
        }


class AudioBridgePluginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.session = FakeSession()
        self.plugin = AudioBridgePlugin(session=self.session, plugin_id=9)

    async def test_normal_offer_path_uses_configure(self) -> None:
        await self.plugin.negotiate(Jsep(type="offer", sdp="v=0\r\n"))
        sent = self.session.messages[-1]
        self.assertEqual(sent.body, {"request": "configure"})
        self.assertEqual(sent.jsep.type, "offer")

    async def test_reversed_offer_and_answer_paths(self) -> None:
        await self.plugin.request_offer(room=1234)
        self.assertEqual(
            self.session.messages[-1].body,
            {"request": "join", "room": 1234, "generate_offer": True},
        )
        await self.plugin.answer_offer(Jsep(type="answer", sdp="v=0\r\n"))
        self.assertEqual(self.session.messages[-1].body, {"request": "configure"})
        self.assertEqual(self.session.messages[-1].jsep.type, "answer")

    async def test_reversed_plain_rtp_is_empty_then_completed(self) -> None:
        await self.plugin.request_offer(room=1234, plain_rtp=True)
        self.assertEqual(self.session.messages[-1].body["rtp"], {})
        await self.plugin.complete_plain_rtp(
            AudioBridgeRtpTransport(ip="192.0.2.8", port=5004)
        )
        self.assertEqual(
            self.session.messages[-1].body["rtp"],
            {"ip": "192.0.2.8", "port": 5004},
        )

    async def test_generate_offer_rejects_client_jsep(self) -> None:
        with self.assertRaises(AudioBridgeProtocolError):
            await self.plugin.join(
                AudioBridgeJoinRequest(room=1, generate_offer=True),
                jsep=Jsep(type="offer", sdp="v=0\r\n"),
            )

    async def test_plain_rtp_rejects_jsep(self) -> None:
        with self.assertRaises(AudioBridgeProtocolError):
            await self.plugin.configure(
                AudioBridgeConfigureRequest(rtp=AudioBridgeRtpTransport()),
                jsep=Jsep(type="offer", sdp="v=0\r\n"),
            )


if __name__ == "__main__":
    unittest.main()
