from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest

from stream_orchestrator import (
    InMemoryEventBus,
    InMemoryLockManager,
    InMemoryStreamRepository,
    LifecyclePolicy,
    MediaKind,
    OperationalState,
    OrchestratorService,
    PipelineSpec,
    ProducerState,
    RestartPolicy,
    SourceDriverRegistry,
    SourceSpec,
    StreamController,
    StreamDefinition,
    TrackContract,
)

from .fakes import FakeClock, FakeDriver, FakeMountpoints


@dataclass(slots=True)
class StackHarness:
    service: OrchestratorService
    mountpoints: FakeMountpoints
    driver: FakeDriver
    clock: FakeClock
    record_id: UUID


async def make_stack(
    *,
    restart: RestartPolicy | None = None,
) -> StackHarness:
    clock = FakeClock()
    repository = InMemoryStreamRepository(clock=clock)
    events = InMemoryEventBus()
    mountpoints = FakeMountpoints()
    driver = FakeDriver()
    drivers = SourceDriverRegistry()
    drivers.register(driver)
    controller = StreamController(
        repository=repository,
        mountpoints=mountpoints,
        drivers=drivers,
        locks=InMemoryLockManager(),
        events=events,
        clock=clock,
    )
    service = OrchestratorService(
        repository=repository,
        controller=controller,
        clock=clock,
    )
    definition = StreamDefinition(
        name="test",
        source=SourceSpec(kind="uri", locator="file:///tmp/demo.mp4"),
        pipeline=PipelineSpec(driver=driver.name, profile="test"),
        tracks=(
            TrackContract(
                mid="video",
                kind=MediaKind.VIDEO,
                codec="h264",
                payload_type=96,
                clock_rate=90_000,
            ),
        ),
        lifecycle=LifecyclePolicy(restart=restart or RestartPolicy()),
    )
    record = await service.define(definition)
    return StackHarness(service, mountpoints, driver, clock, record.id)


@pytest.fixture
async def stack() -> StackHarness:
    return await make_stack()


@pytest.mark.asyncio
async def test_reconcile_creates_one_generation_and_enables_when_media_flows(
    stack: StackHarness,
) -> None:
    await stack.service.request_start(stack.record_id)

    first = await stack.service.reconcile(stack.record_id)
    assert first.status.operational is OperationalState.PENDING
    assert stack.mountpoints.created == 1
    assert stack.driver.started == 1

    stack.mountpoints.flowing = True
    ready = await stack.service.reconcile(stack.record_id)
    assert ready.status.operational is OperationalState.READY
    assert stack.mountpoints.enabled is True

    again = await stack.service.reconcile(stack.record_id)
    assert again.status.operational is OperationalState.READY
    assert stack.mountpoints.created == 1
    assert stack.driver.started == 1


@pytest.mark.asyncio
async def test_stop_is_idempotent(stack: StackHarness) -> None:
    await stack.service.request_start(stack.record_id)
    await stack.service.reconcile(stack.record_id)
    stack.mountpoints.flowing = True
    await stack.service.reconcile(stack.record_id)

    await stack.service.request_stop(stack.record_id)
    stopped = await stack.service.reconcile(stack.record_id)
    assert stopped.status.operational is OperationalState.STOPPED
    assert stack.driver.stopped == 1
    assert stack.mountpoints.destroyed is True

    again = await stack.service.reconcile(stack.record_id)
    assert again.status.operational is OperationalState.STOPPED
    assert stack.driver.stopped == 1


@pytest.mark.asyncio
async def test_failure_honors_backoff_before_restarting(stack: StackHarness) -> None:
    await stack.service.request_start(stack.record_id)
    await stack.service.reconcile(stack.record_id)

    stack.driver.state = ProducerState.FAILED
    stack.driver.healthy = False
    stack.driver.reason = "input lost"
    failed = await stack.service.reconcile(stack.record_id)

    assert failed.status.producer is ProducerState.BACKING_OFF
    assert failed.status.next_retry_at is not None
    assert stack.driver.started == 1
    assert stack.driver.stopped == 1

    unchanged = await stack.service.reconcile(stack.record_id)
    assert unchanged.status.producer is ProducerState.BACKING_OFF
    assert stack.driver.started == 1

    stack.driver.state = ProducerState.RUNNING
    stack.driver.healthy = True
    stack.driver.reason = None
    stack.clock.advance_to(failed.status.next_retry_at)
    restarted = await stack.service.reconcile(stack.record_id)

    assert restarted.status.producer is ProducerState.RUNNING
    assert stack.driver.started == 2


@pytest.mark.asyncio
async def test_restart_attempts_are_latched_until_explicit_start() -> None:
    stack = await make_stack(
        restart=RestartPolicy(
            mode="on-failure",
            maximum_attempts=1,
            initial_delay_seconds=1,
            maximum_delay_seconds=1,
        )
    )
    await stack.service.request_start(stack.record_id)
    await stack.service.reconcile(stack.record_id)

    stack.driver.state = ProducerState.FAILED
    stack.driver.healthy = False
    first_failure = await stack.service.reconcile(stack.record_id)
    assert first_failure.status.producer is ProducerState.BACKING_OFF
    assert first_failure.status.next_retry_at is not None

    stack.clock.advance_to(first_failure.status.next_retry_at)
    await stack.service.reconcile(stack.record_id)
    terminal = await stack.service.reconcile(stack.record_id)
    assert terminal.status.operational is OperationalState.FAILED
    assert terminal.status.producer is ProducerState.FAILED
    starts_at_terminal = stack.driver.started

    latched = await stack.service.reconcile(stack.record_id)
    assert latched.status.operational is OperationalState.FAILED
    assert stack.driver.started == starts_at_terminal

    stack.driver.state = ProducerState.RUNNING
    stack.driver.healthy = True
    await stack.service.request_start(stack.record_id)
    restarted = await stack.service.reconcile(stack.record_id)
    assert restarted.status.producer is ProducerState.RUNNING
    assert stack.driver.started == starts_at_terminal + 1


@pytest.mark.asyncio
async def test_clean_end_does_not_restart_under_on_failure_policy(stack: StackHarness) -> None:
    await stack.service.request_start(stack.record_id)
    await stack.service.reconcile(stack.record_id)

    stack.driver.state = ProducerState.STOPPED
    stack.driver.healthy = False
    ended = await stack.service.reconcile(stack.record_id)

    assert ended.status.operational is OperationalState.STOPPED
    assert ended.status.producer is ProducerState.STOPPED
    starts_at_end = stack.driver.started

    again = await stack.service.reconcile(stack.record_id)
    assert again.status.operational is OperationalState.STOPPED
    assert stack.driver.started == starts_at_end


@pytest.mark.asyncio
async def test_mountpoint_loss_stops_and_retargets_source(stack: StackHarness) -> None:
    await stack.service.request_start(stack.record_id)
    await stack.service.reconcile(stack.record_id)
    first_targets = stack.driver.started_targets[-1]

    stack.mountpoints.exists = False
    missing = await stack.service.reconcile(stack.record_id)
    assert missing.status.mountpoint_ref is None
    assert missing.status.source_ref is None
    assert stack.driver.stopped == 1

    recreated = await stack.service.reconcile(stack.record_id)
    assert recreated.status.generation == 2
    assert stack.mountpoints.created == 2
    assert stack.driver.started == 2
    assert stack.driver.started_targets[-1] != first_targets
