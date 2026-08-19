from __future__ import annotations

from stream_orchestrator import (
    PreparedSource,
    ProducerState,
    SourceContext,
    SourceObservation,
    SourceRuntimeRef,
    StreamDefinition,
)

from .backend import NATIVE_RTSP_DRIVER


class NativeRtspSourceDriver:
    """No-process driver: Janus itself owns the RTSP pull lifecycle."""

    name = NATIVE_RTSP_DRIVER

    async def prepare(
        self,
        context: SourceContext,
        definition: StreamDefinition,
    ) -> PreparedSource:
        if definition.pipeline.driver != self.name:
            raise ValueError(f"expected pipeline.driver={self.name!r}")
        if definition.source.kind != "rtsp" or not definition.source.locator:
            raise ValueError("native Janus RTSP requires an rtsp source with a locator")
        return PreparedSource(
            driver=self.name,
            payload={
                "stream_id": str(context.stream_id),
                "generation": context.generation,
            },
        )

    async def start(self, prepared: PreparedSource, *, generation: int) -> SourceRuntimeRef:
        return SourceRuntimeRef(
            driver=self.name,
            instance_id=f"janus-native-rtsp-g{generation}",
            generation=generation,
            metadata=dict(prepared.payload),
        )

    async def inspect(self, ref: SourceRuntimeRef) -> SourceObservation:
        del ref
        # Mountpoint packet freshness remains the authoritative media check.
        return SourceObservation(state=ProducerState.RUNNING, healthy=True)

    async def stop(self, ref: SourceRuntimeRef, *, deadline_seconds: float) -> None:
        del ref, deadline_seconds

    async def cleanup(self, prepared: PreparedSource) -> None:
        del prepared
