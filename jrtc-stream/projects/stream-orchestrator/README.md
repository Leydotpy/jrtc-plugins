# stream-orchestrator

`stream-orchestrator` is the framework-neutral lifecycle engine for the modular
Janus streaming stack. It does **not** import Janus, Django, Qt, FFmpeg,
GStreamer, SRS, Docker, or Kubernetes.

It owns only stable domain concepts and ports:

- desired state versus observed state;
- logical streams and generations;
- source drivers and source readiness gates;
- mountpoint backends;
- idempotent reconciliation;
- optimistic concurrency;
- per-stream locking and fencing;
- typed events;
- in-memory reference adapters for tests and desktop applications.

Concrete packages plug into these protocols. For example,
`janus-stream-orchestrator` supplies a Janus mountpoint backend,
`stream-orchestrator-ffmpeg` supplies a source driver, and
`stream-orchestrator-django` supplies persistence and web integration.

## Minimal composition

```python
from stream_orchestrator import (
    InMemoryEventBus,
    InMemoryLockManager,
    InMemoryStreamRepository,
    OrchestratorService,
    SourceDriverRegistry,
    StreamController,
    SystemClock,
)

clock = SystemClock()
repository = InMemoryStreamRepository(clock=clock)
drivers = SourceDriverRegistry()

controller = StreamController(
    repository=repository,
    mountpoints=my_mountpoint_backend,
    drivers=drivers,
    locks=InMemoryLockManager(),
    events=InMemoryEventBus(),
    clock=clock,
)
service = OrchestratorService(repository=repository, controller=controller)
```

The application registers drivers and chooses when reconciliation runs. A
server typically runs the provided `Reconciler`; a desktop application may
call `service.reconcile(stream_id)` explicitly.
