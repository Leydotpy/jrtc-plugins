from __future__ import annotations

from stream_orchestrator import (
    PreparedSource,
    ProducerState,
    SourceContext,
    SourceObservation,
    SourceRuntimeRef,
    StreamDefinition,
)

from .models import CommandBuilder, ProcessExecutor, ProcessRef, ProcessSpec


class ProcessSourceDriver:
    def __init__(
        self,
        *,
        name: str,
        executor: ProcessExecutor,
        builder: CommandBuilder,
    ) -> None:
        self.name = name
        self._executor = executor
        self._builder = builder

    async def prepare(
        self,
        context: SourceContext,
        definition: StreamDefinition,
    ) -> PreparedSource:
        spec = self._builder.build(context, definition)
        if not isinstance(spec, ProcessSpec):
            raise TypeError("command builder must return ProcessSpec")
        return PreparedSource(driver=self.name, payload=spec)

    async def start(self, prepared: PreparedSource, *, generation: int) -> SourceRuntimeRef:
        if prepared.driver != self.name or not isinstance(prepared.payload, ProcessSpec):
            raise TypeError("prepared source belongs to a different driver")
        ref = await self._executor.start(prepared.payload)
        return SourceRuntimeRef(
            driver=self.name,
            instance_id=ref.instance_id,
            generation=generation,
            metadata={"executor": ref.executor},
        )

    async def inspect(self, ref: SourceRuntimeRef) -> SourceObservation:
        process_ref = ProcessRef(
            executor=str(ref.metadata.get("executor", self._executor.name)),
            instance_id=ref.instance_id,
        )
        try:
            observation = await self._executor.inspect(process_ref)
        except LookupError:
            return SourceObservation(
                state=ProducerState.FAILED,
                healthy=False,
                reason="process is no longer known to its executor",
            )
        if observation.running:
            return SourceObservation(
                state=ProducerState.RUNNING,
                healthy=True,
                progress_at=observation.heartbeat_at,
            )
        return SourceObservation(
            state=ProducerState.FAILED if observation.exit_code else ProducerState.STOPPED,
            healthy=False,
            progress_at=observation.heartbeat_at,
            exit_code=observation.exit_code,
            reason=f"process exited with code {observation.exit_code}",
        )

    async def stop(self, ref: SourceRuntimeRef, *, deadline_seconds: float) -> None:
        process_ref = ProcessRef(
            executor=str(ref.metadata.get("executor", self._executor.name)),
            instance_id=ref.instance_id,
        )
        try:
            await self._executor.terminate(process_ref, grace_seconds=deadline_seconds)
        except LookupError:
            return

    async def cleanup(self, prepared: PreparedSource) -> None:
        return None
