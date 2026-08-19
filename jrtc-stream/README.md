# Modular Janus Streaming workspace

This workspace implements a deliberately decoupled Python architecture for:

1. providing the Janus Streaming named-plugin distribution for `jrtc`;
2. orchestrating source lifecycles without depending on Janus;
3. connecting the two through an optional bridge;
4. adding source engines and application frameworks as separate packages.

It is a tested reference implementation and reviewable foundation, not a claim
that a deployment is production-ready before real Janus, SRS, FFmpeg,
GStreamer, camera, browser, network, load, and failure-injection tests pass.

## Package graph

```text
stream-orchestrator                         stdlib-only domain/application core
├── stream-orchestrator-process             safe process execution adapter
│   ├── stream-orchestrator-ffmpeg          FFmpeg profiles and command builder
│   └── stream-orchestrator-gstreamer       GStreamer profiles and builder
├── stream-orchestrator-srs                 SRS readiness/API/grant adapter
├── stream-orchestrator-django              Django persistence/lifespan adapter
└── stream-orchestrator-qt                  Qt-safe async bridge

jrtc-stream                         Streaming plugin + standalone client

janus-stream-orchestrator                   optional bridge depending on both
├── stream-orchestrator
└── jrtc-stream
```

No framework integration depends on Janus. No source engine depends on Django
or Qt. Applications choose and compose only the packages they need.

## Packages

| Distribution | Import | Purpose | Python |
|---|---|---|---|
| `stream-orchestrator` | `stream_orchestrator` | Desired/observed state, ports, controller, reconciler | 3.12+ |
| `stream-orchestrator-process` | `stream_orchestrator_process` | Shell-free subprocess executor and process driver | 3.12+ |
| `stream-orchestrator-ffmpeg` | `stream_orchestrator_ffmpeg` | Profile-driven FFmpeg adapter | 3.12+ |
| `stream-orchestrator-gstreamer` | `stream_orchestrator_gstreamer` | Profile-driven GStreamer adapter | 3.12+ |
| `stream-orchestrator-srs` | `stream_orchestrator_srs` | SRS API, source gate, callbacks, publish grants | 3.12+ |
| `jrtc-stream` | `janus_streaming` | Streaming plugin entry point, protocol models/helpers, administration, and viewer signaling | 3.14+ |
| `janus-stream-orchestrator` | `janus_stream_orchestrator` | Janus implementation of the mountpoint port | 3.14+ |
| `stream-orchestrator-django` | `stream_orchestrator_django` | Django ORM/event/lifespan adapters | 3.12+ |
| `stream-orchestrator-qt` | `stream_orchestrator_qt` | Dedicated asyncio thread and optional Qt signals | 3.12+ |

## Workspace setup

The complete workspace standardizes development and verification on Python 3.14.

```bash
uv python install 3.14
uv sync --all-packages --group dev
uv run make verify
```

Individual non-Janus packages remain installable on Python 3.12+.

## Composition examples

A service application normally creates:

```text
repository + lock manager + event publisher
                  │
                  ▼
          StreamController
      ┌───────────┴────────────┐
      ▼                        ▼
MountpointBackend       SourceDriverRegistry
      │                        │
optional Janus bridge     FFmpeg/GStreamer/native/etc.
```

See `examples/` and `docs/COMPOSITION.md`.

## Verification

```bash
make lint
make boundaries
make test
make typecheck
make build
```

The Codex review protocol and non-negotiable architecture rules are in
`AGENTS.md`. Construction-environment evidence and explicitly open release
gates are recorded in `VERIFICATION.md`.
