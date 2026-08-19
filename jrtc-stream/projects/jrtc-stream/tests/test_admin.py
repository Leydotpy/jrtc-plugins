from __future__ import annotations

import pytest

from janus_streaming import AudioTrackSpec, RtpMountpointSpec, StreamingAdminClient

from .fakes import FakeHandle, event_response


@pytest.mark.asyncio
async def test_admin_list_and_create_are_normalized(monkeypatch):
    handle = FakeHandle(
        [
            event_response(
                {
                    "list": [
                        {
                            "id": 10,
                            "type": "rtp",
                            "description": "main",
                            "enabled": True,
                            "media": [
                                {
                                    "mid": "audio",
                                    "type": "audio",
                                    "age_ms": 5,
                                    "pt": 111,
                                    "codec": "opus",
                                }
                            ],
                        }
                    ]
                }
            ),
            event_response(
                {
                    "create": "created",
                    "permanent": False,
                    "stream": {
                        "id": 11,
                        "type": "rtp",
                        "description": "new",
                        "is_private": True,
                        "ports": [{"type": "audio", "mid": "audio", "port": 5004}],
                    },
                }
            ),
        ]
    )

    async def factory(*args, **kwargs):
        return handle

    client = StreamingAdminClient(object(), handle_factory=factory)
    await client.start()
    values = await client.list_mountpoints()
    assert values[0].media[0].payload_type == 111
    created = await client.create_rtp(
        RtpMountpointSpec(
            description="new",
            media=(AudioTrackSpec(mid="audio"),),
        )
    )
    assert created.id == 11
    assert created.ports[0].port == 5004
