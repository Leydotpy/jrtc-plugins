# AGENTS.md

## Scope and authority

This file applies to the entire repository. It is the controlling instruction
file for Codex and other coding agents working in this workspace. More-specific
`AGENTS.md` files may add constraints inside a package, but they may not weaken
or reverse the dependency, security, testing, or release rules here.

## Mission

Analyze, verify, cross-reference, harden, and complete this workspace as a set
of independently publishable Python projects for Janus Streaming and media
source orchestration.

The intended result is **modular composition**, not a monolith:

- `jrtc-stream` is a standalone named-plugin distribution built on
  plugin-agnostic `jrtc`.
- `stream-orchestrator` is a framework-neutral source/mountpoint lifecycle core.
- `janus-stream-orchestrator` is the optional bridge between those two projects.
- source engines and external systems are separate adapter projects.
- Django and Qt integrations are separate projects that depend on the
  orchestration layer, not on Janus.
- the final host application chooses which pieces to install and compose.

Do not describe the repository as production-ready merely because unit tests
pass. Production readiness requires the real integration, failure, load, and
security gates in `docs/RELEASE_GATES.md`.

## Read before changing code

Read these files in order:

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `docs/UPSTREAM_COMPATIBILITY.md`
4. `docs/SECURITY.md`
5. `docs/OPERATIONS.md`
6. `docs/KNOWN_LIMITATIONS.md`
7. `docs/RELEASE_GATES.md`
8. `VERIFICATION.md` as historical evidence, not as a substitute for rerunning
   checks in the current environment
9. the `README.md` and `pyproject.toml` of every package affected by the task

Use `docs/SOURCES.md` as the primary-source starting point. For any current
upstream behavior, inspect the exact installed/downloaded version rather than
relying on memory or a secondary article.

## Non-negotiable dependency graph

The graph below is an architectural invariant:

```text
stream-orchestrator                         standard library only
├── stream-orchestrator-process             depends on core
│   ├── stream-orchestrator-ffmpeg          depends on core + process
│   └── stream-orchestrator-gstreamer       depends on core + process
├── stream-orchestrator-srs                 depends on core
├── stream-orchestrator-django              depends on core + Django
└── stream-orchestrator-qt                  depends on core; Qt is optional

jrtc-stream                         depends on jrtc + Pydantic

janus-stream-orchestrator                   depends on core + jrtc-stream
```

The following are forbidden:

- `stream-orchestrator` importing Janus, Django, Qt, Pydantic, HTTP clients, or
  subprocess/media-engine modules;
- `jrtc-stream` importing the orchestration core or an application
  framework;
- Django or Qt packages importing `janus_streaming` or
  `janus_stream_orchestrator`;
- FFmpeg, GStreamer, process, or SRS packages importing Django or Qt;
- moving bridge logic into either independent upstream package;
- making an integration package a mandatory dependency of the core;
- using undeclared imports or `PYTHONPATH` tricks to bypass package metadata.

Run `python scripts/check_boundaries.py` after every dependency-affecting
change. Update the boundary checker only when an explicitly approved
architectural change is made; never weaken it merely to make a failing change
pass.

## Package responsibilities

### `stream-orchestrator`

Owns stable domain models, ports, desired/observed state, reconciliation,
restart policy, event abstractions, repository abstractions, and a small
intent-oriented service API.

Required invariants:

- one logical stream may have multiple concrete generations;
- a source runtime is distinct from a mountpoint;
- a managed source targets exactly one concrete mountpoint generation;
- a missing/replaced mountpoint requires stopping and retargeting its source;
- process health does not imply media health;
- required track packet freshness determines readiness;
- when no track contract is declared, at least one observed fresh track is
  required before readiness;
- clean end-of-stream and exhausted failures are terminal/latching states until
  an explicit start request resets them;
- retry delays are bounded, jittered, and honored before another attempt;
- reconciliation is idempotent and cancellation-safe;
- repository writes use optimistic concurrency;
- in-memory implementations are never presented as distributed locks or
  durable production storage.

Do not add source-specific schemas to the core. Adapter packages validate their
own settings and translate them to `SourceSpec`/`PipelineSpec`.

### `stream-orchestrator-process`

Owns shell-free process execution and the generic process-backed source driver.

Required invariants:

- use argument vectors; never `shell=True`;
- support executable allowlisting;
- bound captured stdout/stderr;
- own and terminate process groups where supported;
- terminate gracefully before force-killing;
- never block the event loop with process I/O;
- do not claim durable supervision after the Python process exits;
- expose enough observation data for progress and failure diagnosis without
  leaking secrets.

### `stream-orchestrator-ffmpeg`

Owns named FFmpeg profiles and command construction. Do not expose arbitrary
raw arguments through a public/untrusted API. Use FFmpeg machine-readable
progress where practical. Validate file roots and locator schemes. Keep codec,
payload type, keyframe, timestamp, and packetization assumptions explicit and
integration-tested.

### `stream-orchestrator-gstreamer`

Owns named GStreamer profiles and structured pipeline construction. Do not
accept untrusted free-form pipelines. For a production native integration,
observe `GstBus` errors/EOS/state changes and prefer process isolation for
crash containment. A `gst-launch-1.0` adapter is a valid process boundary, not
proof that all native GStreamer lifecycle cases are covered.

### `stream-orchestrator-srs`

Owns SRS API observation, callback parsing, publisher readiness gates, and
application-level publish grants. It does not own an encoder bridge.

Required invariants:

- callbacks are hints/wakeups, not authoritative state;
- reconcile callback events with the SRS API;
- authenticate callback senders in the host application;
- reject malformed/unsupported callback actions;
- publishing tokens must be enforced by a reverse proxy/callback/application
  layer; token generation by itself is not authorization;
- never log stream keys or bearer tokens.

### `jrtc-stream`

Owns the concrete Streaming plugin class and entry point, all Streaming request
and response models and convenience helpers, stable domain models, a reusable administrative client, viewer
negotiation/state, lifecycle helpers, timeouts, error translation, and response
normalization.

Required invariants:

- all direct `jrtc` imports remain in
  `janus_streaming/_compat.py`;
- publish exactly one concrete `streaming` plugin class through the
  `jrtc.plugins` entry-point group;
- do not rely on a named Streaming class, helper, request model, or response
  model from core;
- keep the public administration/viewer layer composed around the package's
  concrete plugin handle;
- one viewer object/handle represents one PeerConnection;
- administrative handle reuse is bounded by a semaphore;
- `watch` returns an offer and `start` carries the answer;
- resume uses `start` without a new JSEP where supported;
- handle cleanup is idempotent;
- user-facing models do not expose unstable upstream model classes;
- secrets and admin keys never appear in ordinary responses/logs;
- operation and negotiation timeouts are explicit;
- transport-level behavior such as unsolicited trickle must be fixed/tested at
  the transport boundary, not hidden in orchestration code.

When changing compatibility code, inspect the exact `jrtc`
wheel/source and add contract tests for every changed request field, entry-point
contract, and response shape.

### `janus-stream-orchestrator`

Owns only adaptation between the orchestration `MountpointBackend`/driver ports
and `jrtc-stream`.

Required invariants:

- management and RTSP credential values come from injected resolvers;
- serialized mountpoint metadata may contain references/IDs, never secret
  values;
- create mountpoints disabled, start/observe the source, then enable only after
  required media is fresh;
- map only the Janus missing-mountpoint error to `exists=False`; propagate
  authorization, validation, and transport failures;
- dynamic RTP targets must match all requested `mid` values;
- do not invent an RTCP target when Janus did not return/configure one;
- native RTSP is represented by a no-process source driver, while Janus packet
  freshness remains the readiness authority;
- do not import Django, Qt, SRS, FFmpeg, or GStreamer.

### `stream-orchestrator-django`

Owns Django persistence, durable event/outbox models, optional ASGI lifespan
plumbing, and explicit service registration. It must not select a mountpoint
backend or source engine.

Required invariants:

- no network I/O in `AppConfig.ready()`;
- optimistic concurrency is enforced in the database update predicate;
- migrations match models (`makemigrations --check`);
- async ORM calls are used from async methods;
- transactional multi-step business operations are isolated deliberately;
- command endpoints return accepted intent quickly in distributed deployments;
- authentication, authorization, tenant isolation, rate limits, and callback
  verification remain host-application responsibilities and must be documented;
- do not import Janus packages.

### `stream-orchestrator-qt`

Owns a safe bridge between GUI code and async orchestration. The base package
must not require a Qt binding. Optional PySide6/PyQt6 modules must emit queued
signals so GUI mutations occur on the GUI thread. Never block the GUI thread on
`Future.result()` or run long network/process work there.

## Upstream verification protocol

For Janus-related changes:

1. Record the exact `jrtc` and Janus versions tested.
2. Download/inspect the exact wheel/source.
3. Verify constructor fields for every Streaming request used.
4. Verify plugin attach/send/trickle/detach behavior.
5. Verify synchronous versus asynchronous plugin replies.
6. Verify error constants, especially missing mountpoint.
7. Verify dynamic RTP creation response fields and RTCP behavior.
8. Verify unsolicited events, trickle ICE, media/webrtcup/slowlink/hangup paths.
9. Run real Janus and browser integration tests.
10. Update `docs/UPSTREAM_COMPATIBILITY.md` and the changelog.

For SRS/FFmpeg/GStreamer/Django/Qt changes, use the same principle: primary
source, exact version, contract/integration evidence, documented matrix.

## Development workflow

### Environment

The complete workspace currently standardizes development on Python 3.14.

```bash
uv python install 3.14
uv sync --all-packages --group dev
```

Non-Janus packages must retain their declared Python 3.12+ compatibility unless
an approved breaking change is made.

### Baseline before edits

Run and record:

```bash
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_boundaries.py
uv run python scripts/run_tests.py
uv run mypy projects/stream-orchestrator/src \
  projects/stream-orchestrator-process/src \
  projects/stream-orchestrator-ffmpeg/src \
  projects/stream-orchestrator-gstreamer/src \
  projects/stream-orchestrator-srs/src \
  projects/stream-orchestrator-qt/src
uv run python -m compileall -q projects scripts examples
```

If baseline failures exist, distinguish pre-existing failures from regressions
and explain both. Do not hide failures by deleting tests, weakening lint rules,
or broadening exception handling.

### Change process

1. State the affected package(s) and why the change belongs there.
2. Identify public API and dependency implications.
3. Add/adjust tests before or with the implementation.
4. Implement the smallest coherent change.
5. Run package-local tests.
6. Run the complete boundary/lint/type/test/build suite.
7. Update documentation and changelog for externally observable behavior.
8. Report evidence, unresolved risks, and integration work still required.

## Coding standards

- Prefer explicit composition and protocols over inheritance and global state.
- Keep public models immutable where practical.
- Use monotonic deadlines for elapsed-time logic; wall-clock timestamps are for
  persistence and observability.
- Preserve cancellation; catch `asyncio.CancelledError` only to perform bounded,
  shielded cleanup, then re-raise.
- Bound queues, concurrency, retries, output capture, and shutdown waits.
- Use structured errors with stable machine-readable reason codes.
- Never silently swallow an authorization, validation, or protocol error.
- Cleanup methods are idempotent.
- Avoid bare `except:` and broad `except Exception` unless the boundary records
  failure state and deliberately translates/re-raises.
- No mutable module-level runtime singleton unless it is an explicit registry
  with documented lifecycle.
- Avoid import-time network, process, database, or event-loop side effects.
- Do not place live event-loop objects, handles, processes, or queues in Redis,
  Django models, JSON, or cross-process messages.
- Public APIs require type hints and docstrings for non-obvious lifecycle rules.
- Maintain `py.typed` in every typed package.
- Keep line length and lint rules in `pyproject.toml`.

## Concurrency and crash-recovery review

For every lifecycle operation, analyze these points explicitly:

- What if the command is delivered twice?
- What if the remote operation succeeds but the response is lost?
- What if the process dies after persistence but before remote action?
- What if the process dies after remote action but before persistence?
- What if two reconcilers act concurrently?
- What stale actor can still write after losing a lock?
- What resource is leaked after cancellation?
- What deadline bounds the operation?
- What observation proves success?
- How does restart/reconciliation converge?

Distributed adapters must use fencing tokens or another equivalent stale-writer
protection. Process-local locks are insufficient for multi-worker deployment.

## Testing requirements

### Unit and contract tests

Cover at minimum:

- domain validation and serialization round trips;
- repository create/get/list/CAS/delete conflicts;
- idempotent start/stop/reconcile;
- backoff is honored and bounded;
- exhausted restart is latched;
- clean end-of-stream does not restart under `on-failure`;
- explicit start resets terminal state;
- source start/prepare failure schedules or latches correctly;
- missing mountpoint stops and retargets the source;
- track freshness and partial-track failure;
- gate waiting/readiness;
- cancellation cleanup;
- shell-free command generation and locator allowlists;
- bounded process logs and graceful/forced termination;
- SRS callback/grant/API errors;
- Janus request JSON and response normalization;
- viewer state transitions and duplicate/out-of-order messages;
- missing Janus mountpoint versus unauthorized/other errors;
- Django migrations, CAS, event/outbox behavior;
- Qt runner shutdown and GUI-signal handoff.

### Integration tests

Use markers such as `integration`, `janus`, `srs`, `ffmpeg`, `gstreamer`,
`browser`, and `failure`. Integration tests must be runnable locally or in CI
through documented containers/services. Do not replace a real media test with a
fake SDP test and call it equivalent.

### Property/state-machine tests

Add state-machine or property tests for orchestration transitions, duplicate
commands, cancellation points, and serialization where they materially improve
coverage.

### Load and soak tests

Measure source startup rate, concurrent mountpoint control, packet/media
readiness latency, viewer count, process/resource leakage, reconnect storms, and
long-running stability. Record environment and thresholds.

## Security review checklist

Before final approval, verify:

- source URL SSRF and DNS-rebinding controls;
- file-root and device allowlists;
- command/profile injection resistance;
- callback authentication, replay protection, and idempotency;
- short-lived publisher grants and revocation behavior;
- secret references and redaction;
- no SDP/ICE/credentials in default logs;
- administrative/viewer permission separation;
- tenant isolation and per-tenant quotas;
- RTP/SRTP/network policy;
- process/container sandboxing and resource limits;
- dependency, image, license, and SBOM review.

Do not add a convenience feature that weakens these controls without a clearly
documented, opt-in unsafe mode and tests proving the default remains safe.

## Packaging and versioning

Each directory under `projects/` is independently publishable.

- Build each wheel and sdist independently.
- Test installation in a clean environment using only declared dependencies.
- Keep distribution names and import names stable.
- Follow semantic versioning for public APIs.
- Keep bridge dependency ranges narrow until compatibility CI proves widening.
- Do not synchronize package versions merely for convenience; version only
  packages with externally observable changes.
- Verify wheels include `py.typed`, README metadata, and no tests/cache/secrets.
- Generate hashes and an SBOM for release artifacts.
- Never publish to an index or push a release tag without explicit human
  authorization.

Build all packages with:

```bash
uv run python scripts/build_all.py
uv run python scripts/verify_artifacts.py
```

## Definition of done for a Codex review

A review is complete only when the final report contains:

1. exact package/version/environment inventory;
2. architecture and dependency-boundary findings;
3. upstream cross-reference findings with primary sources;
4. correctness findings ranked by severity;
5. concurrency/crash-recovery findings;
6. security findings;
7. performance/resource findings;
8. packaging/API/versioning findings;
9. tests added and commands run with results;
10. real integration tests run, or an explicit list of those not run;
11. patches made, with affected packages;
12. remaining limitations and a release recommendation.

Use severity levels `critical`, `high`, `medium`, `low`, and `informational`.
Every finding must include evidence, impact, affected code, and a concrete
remediation. Do not mark a finding resolved without a test or other verifiable
evidence.

## Initial review priorities for this generated workspace

Begin with these known high-value verification items:

1. Run on real Python 3.14 with the unmodified `jrtc` dependency.
2. Confirm every owned request model and `_compat.py` call against
   `jrtc` 3.x and the targeted Janus release.
3. Add real Janus contract/integration/browser tests, including full trickle.
4. Add tests for all restart/backoff/terminal/mountpoint-loss branches.
5. Add a fenced distributed lock and durable worker/repository reference
   implementation before multi-worker claims.
6. Test Django migrations and repository CAS on PostgreSQL, not only SQLite.
7. Implement/verify a durable process/container/remote-agent executor.
8. Validate FFmpeg and GStreamer profiles with actual RTP received by Janus.
9. Validate SRS browser and OBS publication with authenticated callbacks.
10. Perform failure injection, load, soak, and security review before release.

Preserve modularity while resolving these items. The correct solution is almost
never to merge packages or move application-specific choices into the core.
