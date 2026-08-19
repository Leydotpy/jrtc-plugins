from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from stream_orchestrator import PipelineSpec, SourceSpec, StreamDefinition

from stream_orchestrator_srs import HmacPublishGrantIssuer, SrsClient, SrsPublisherGate


@pytest.mark.asyncio
async def test_gate_detects_publisher():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": 0,
                "streams": [
                    {
                        "id": "stream-id",
                        "name": "main",
                        "app": "live",
                        "vhost": "__defaultVhost__",
                        "publish": {"active": True, "cid": "client-1"},
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(base_url="http://srs", transport=transport)
    client = SrsClient(base_url="http://srs", client=http_client)
    gate = SrsPublisherGate(client)
    definition = StreamDefinition(
        name="main",
        source=SourceSpec(
            kind="srs-publisher",
            locator="http://srs:8080/live/main.flv",
            settings={"app": "live", "stream": "main"},
        ),
        pipeline=PipelineSpec(driver="ffmpeg", profile="h264-opus-low-latency"),
        tracks=(),
    )
    observation = await gate.inspect(definition)
    assert observation.ready is True
    await http_client.aclose()


def test_signed_grant_round_trip_and_expiry():
    issuer = HmacPublishGrantIssuer(
        secret=b"x" * 32,
        publish_base_url="https://publish.example.test",
    )
    now = datetime(2026, 7, 11, tzinfo=UTC)
    stream_id = uuid4()
    grant = issuer.issue(
        stream_id=stream_id,
        app="live",
        stream="main",
        protocol="whip",
        ttl_seconds=60,
        now=now,
    )
    claims = issuer.verify(grant.token, now=now + timedelta(seconds=30))
    assert claims["sub"] == str(stream_id)
    with pytest.raises(ValueError, match="expired"):
        issuer.verify(grant.token, now=now + timedelta(seconds=61))
