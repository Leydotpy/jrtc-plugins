from __future__ import annotations

from stream_orchestrator import GateObservation, ProducerState, StreamDefinition

from .client import SrsClient


class SrsPublisherGate:
    kind = "srs-publisher"

    def __init__(self, client: SrsClient) -> None:
        self._client = client

    async def inspect(self, definition: StreamDefinition) -> GateObservation:
        settings = definition.source.settings
        app = str(settings.get("app", "live"))
        stream = str(settings.get("stream", ""))
        vhost = str(settings.get("vhost", "__defaultVhost__"))
        if not stream:
            raise ValueError("SRS publisher source requires settings['stream']")
        observation = await self._client.inspect_stream(app=app, stream=stream, vhost=vhost)
        if observation.published:
            return GateObservation(
                ready=True,
                state=ProducerState.PREPARING,
                reason="SRS publisher is connected",
            )
        return GateObservation(
            ready=False,
            state=ProducerState.WAITING_FOR_SOURCE,
            reason=f"waiting for SRS publisher {vhost}/{app}/{stream}",
        )
