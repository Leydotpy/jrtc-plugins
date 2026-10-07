# AGENTS.md — jrtc-video Management-Handle and Command-Path Upgrade

## 0. Mission

This package is the VideoRoom-specific JRTC plugin layer.

Implement the changes in this file so that `jrtc-video`:

- keeps its typed VideoRoom request/response API;
- removes unnecessary management-handle attach/detach round trips;
- safely reuses one management/control plugin handle per owning Janus session/service;
- remains natively asynchronous;
- cleanly handles stale/lost sessions;
- never conflates a management handle with participant publisher/subscriber handles;
- exposes lifecycle APIs that applications such as Synq can use without reimplementing VideoRoom internals.

Do not add Synq/Django/Socket.IO/database logic to this package.

---

## 1. Primary code targets

Audit and modify:

- `jrtc-video/src/jrtc_video/service.py`
- the concrete `VideoRoomPlugin` implementation
- VideoRoom request/response model modules
- service/plugin lifecycle tests
- any package exports needed for the reusable service lifecycle

If file layout has changed, locate the active implementations rather than creating duplicate abstractions.

---

## 2. Existing behavior to preserve

The current package has several good characteristics that must remain:

1. typed request objects;
2. typed `VideoRoomReply` responses;
3. VideoRoom protocol validation;
4. JSEP-role validation;
5. plugin commands that wait for the actual VideoRoom event where required;
6. explicit errors rather than untyped dictionaries;
7. application-independent APIs.

Do not weaken these to gain speed.

---

# PART I — PERSISTENT MANAGEMENT HANDLE

## 3. Problem

Room-management commands currently use a short-lived control path conceptually equivalent to:

```text
attach VideoRoom management plugin
    -> perform one command
    -> detach plugin
```

For repeated management operations this adds two unnecessary Janus transactions around every command:

```text
ATTACH -> COMMAND -> DETACH
```

The package should instead support:

```text
lazy ATTACH once
    -> COMMAND
    -> COMMAND
    -> COMMAND
    -> ...
    -> DETACH during service/session shutdown
```

This optimization applies only to VideoRoom management/control operations.

---

## 4. Add a lazily attached reusable management plugin

`VideoRoomService` should own a management plugin reference conceptually like:

```python
self._management_plugin: VideoRoomPlugin | None
```

and an async creation/lifecycle lock:

```python
self._management_lock = asyncio.Lock()
```

The implementation must provide an internal helper equivalent to:

```python
async def _get_management_plugin(self) -> VideoRoomPlugin:
    ...
```

Required behavior:

1. if the cached plugin is attached and its session is healthy, return it;
2. if absent, attach one under the lock;
3. if another coroutine attached while waiting for the lock, reuse that one;
4. if stale/closed/detached, invalidate it and attach a new one;
5. never attach two live management handles for one service/session due to a race.

---

## 5. Reuse the management handle for management operations

Operations that should route through the reusable management handle include, where exposed by the package:

- create room;
- destroy room;
- room existence/query;
- edit room;
- allowed-token management;
- kick;
- moderate;
- list rooms;
- list participants;
- recording controls;
- RTP forwarder management;
- other VideoRoom management commands that do not represent a participant publisher/subscriber media handle.

Do not blindly convert participant/session-role commands to this handle.

---

## 6. Participant handles stay separate

The following must continue to use dedicated participant handles:

- publisher join;
- publisher configure/publish/unpublish;
- subscriber join;
- subscriber update;
- subscriber start;
- ICE trickle for those media handles;
- participant hangup/detach.

A management handle MUST NOT become a shared publisher or subscriber.

Reason:

- Janus plugin-handle role/state is meaningful;
- shared participant state would cause command races and protocol corruption;
- per-participant media ownership must remain explicit.

---

# PART II — SERVICE LIFECYCLE

## 7. Add deterministic async close

If not already present, `VideoRoomService` should expose:

```python
async def aclose(self) -> None:
    ...
```

It should:

1. atomically prevent new management-handle creation once closing starts;
2. detach the reusable management plugin at most once;
3. clear the cached reference;
4. tolerate an already-lost Janus session;
5. not hide the success of prior state-changing commands merely because close/detach cleanup later fails.

Optionally provide:

```python
async def __aenter__(...)
async def __aexit__(...)
```

when that matches package conventions.

---

## 8. Session-loss invalidation

The cached management plugin is valid only while:

- its Janus session generation is active;
- its handle is still attached;
- the service is not closing/closed.

If JRTC signals a lost/replaced session:

- mark the cached management plugin unusable;
- do not try to keep issuing commands on the stale handle;
- lazily create a new management plugin on the replacement session when the next command needs it.

Do not persist a Janus handle ID and attempt to adopt it across an unrelated session generation without a proven JRTC reclaim contract.

---

## 9. Concurrency-safe invalidation

Race to handle explicitly:

```text
command A using management handle
session loss/invalidation
command B starting
service close
```

Use one or more appropriate async locks/state flags.

Do not:

- detach a handle while another command is actively using it unless the underlying JRTC session has already failed;
- allow close and lazy-create to cross and leave a new handle alive after close;
- leak locks or task references.

If JRTC's plugin/registry invocation already serializes per-handle operations, compose with it rather than adding conflicting lock layers.

---

# PART III — COMMAND FAILURE SEMANTICS

## 10. Do not retry state-changing commands merely because cleanup failed

A state-changing management command may have succeeded on Janus even when subsequent local cleanup fails.

With a persistent handle, cleanup normally happens at service close, but the invariant remains:

> Once a state-changing VideoRoom command has been confirmed successful, a later detach/cleanup failure must not cause the application to repeat the command automatically.

Examples:

- create room;
- destroy room;
- edit room;
- kick participant;
- recording changes;
- forwarder changes.

Avoid duplicate side effects.

---

## 11. Decide when a command failure invalidates the management handle

Not every VideoRoom error means the handle is bad.

Examples of domain/protocol responses such as:

- room not found;
- invalid PIN/secret;
- unauthorized operation;

should generally leave a healthy plugin handle reusable.

Transport/session/handle failures such as:

- session lost;
- detached handle;
- closed transport;
- handle not found due to lifecycle loss;

should invalidate the cached management plugin.

Centralize this distinction so callers do not implement their own heuristics.

---

# PART IV — TYPED API INVARIANTS

## 12. Preserve typed request/response behavior

Do not replace package models with unvalidated `dict[str, Any]` payloads for performance.

Maintain:

- strict identifiers;
- VideoRoom request discriminators;
- typed replies;
- correct JSEP validation;
- `wait_for_event=True` for commands whose final VideoRoom event is the authoritative result.

If serialization performance is later a concern, profile before changing model boundaries.

---

## 13. Keep ICE behavior delegated to generic JRTC

`jrtc-video` may expose a convenience method, but it must not implement its own per-candidate batching loop.

If a participant plugin receives:

```python
Sequence[TrickleCandidate]
```

forward the whole sequence to JRTC.

Completion remains a distinct JRTC operation.

Frontend batching policy belongs to Synq.js, not this package.

---

# PART V — APPLICATION INTEGRATION API

## 14. Make the reusable service easy for Synq to own

Synq should not have to instantiate a temporary `VideoRoomPlugin` for each management command.

Provide a clean package-level abstraction such that Synq can hold/cache one `VideoRoomService` per selected Janus session or session-generation.

A suitable API might be:

```python
service = VideoRoomService(session=janus_session)

await service.create_room(...)
await service.list_participants(...)
await service.destroy_room(...)

await service.aclose()
```

Exact constructor signatures should follow the current package design.

Do not expose internal `_management_plugin` as an application-managed object unless there is a compelling existing convention.

---

## 15. Avoid a global singleton

Do not create one process-global VideoRoom management plugin independent of Janus session ownership.

The cached handle must be associated with the correct Janus session/generation.

If the application uses a JRTC session pool, it may have one `VideoRoomService` per pooled session.

---

# PART VI — TEST REQUIREMENTS

## 16. Management handle reuse tests

Add tests proving:

1. first management command attaches one plugin;
2. second management command on same healthy service reuses it;
3. N sequential commands still perform exactly one attach;
4. service close performs one detach;
5. repeated `aclose()` is idempotent.

---

## 17. Concurrent lazy-create tests

Run multiple first-use management commands concurrently.

Assert:

- exactly one management handle is attached;
- all callers use the same live plugin;
- no leaked extra handle remains.

Use barriers/events rather than sleep-based race tests where possible.

---

## 18. Session-loss tests

Simulate:

1. cached management handle on healthy session;
2. session becomes unhealthy/lost;
3. next management command.

Assert:

- stale handle is not reused;
- stale reference is invalidated;
- replacement session can lazily get a new handle;
- no persisted/stale handle ID is silently adopted.

---

## 19. Command error tests

Prove:

- a VideoRoom domain error does not necessarily destroy the reusable management handle;
- a transport/session-lost error does invalidate it;
- state-changing command success is not retried because close/detach later fails;
- typed errors remain stable.

---

## 20. Participant separation tests

Prove:

- management handle ID differs from participant publisher/subscriber handles;
- participant commands never mutate management-handle role state;
- management commands never use participant plugin instances.

---

# PART VII — OBSERVABILITY

## 21. Low-overhead metrics/logs

Make it possible to observe:

- management handle attaches;
- management handle reuses;
- invalidations;
- detach/close attempts;
- command duration;
- command failures by category.

Do not log secrets, full SDP, or candidate strings.

Useful structured fields:

- session ID;
- management handle ID;
- command name;
- duration;
- reused vs attached;
- invalidation reason.

---

# PART VIII — PERFORMANCE ACCEPTANCE

## 22. Benchmark management commands

Compare before/after for repeated operations such as:

```text
list_participants x 100
exists/query x 100
mixed management operations
```

Measure:

- Janus request count;
- p50/p95 command latency;
- attach count;
- detach count;
- CPU;
- handles left attached after shutdown.

Expected architectural improvement:

```text
BEFORE
100 commands ~= 100 attach + 100 command + 100 detach

AFTER
100 commands ~= 1 attach + 100 command + 1 detach
```

Exact counts may vary with recovery events, but healthy steady-state reuse is required.

---

# PART IX — IMPLEMENTATION ORDER

1. Add tests demonstrating repeated management attach/detach.
2. Add lifecycle lock/state and lazy `_management_plugin`.
3. Route management methods through the reusable handle.
4. Add `aclose()` and optional async context-manager support.
5. Add invalidation rules for lost sessions/handles.
6. Add concurrency/session-loss tests.
7. Add metrics.
8. Update package documentation/examples.
9. Coordinate Synq adapter migration to consume the service.

---

# PART X — DEFINITION OF DONE

This upgrade is complete only when:

- healthy repeated management commands reuse one VideoRoom management handle per owning session/service;
- concurrent first use cannot create duplicate handles;
- service close is deterministic and idempotent;
- lost sessions invalidate the handle;
- participant publisher/subscriber handles remain separate;
- typed VideoRoom behavior is preserved;
- no Synq/Django-specific logic leaks into `jrtc-video`;
- tests prove lifecycle, concurrency, failure, and reuse behavior;
- benchmark evidence shows the attach/detach request reduction.
