# Verification report

## `jrtc-stream` 0.2.0 core-split verification

**Verification date:** 2026-07-12  
**Interpreter:** CPython 3.14.0  
**Core candidate:** local `jrtc` 3.0.0

The Streaming package migration was verified with:

- `uv lock` and `uv sync --all-packages --group dev`;
- 15 Streaming unit/contract tests and 38 passing tests across all nine projects;
- workspace-wide Ruff format and lint checks (81 files);
- strict MyPy for all nine `janus_streaming` source files and the 33-file
  framework-neutral source set;
- dependency-boundary and compile checks;
- lazy `jrtc.plugins` entry-point resolution in a fresh process;
- independent wheel and sdist builds for all nine projects using
  `uv build --all-packages --no-sources`;
- strict `twine check`, exact name/version/entry-point validation, and archive
  checks for generated files, local paths, tests in wheels, and token-shaped
  secrets;
- generated SHA-256 manifests and an SPDX 2.3 SBOM;
- clean CPython 3.14 installation of the wheel with local
  `jrtc` 3.0.0, followed by physically removing the two obsolete core
  Streaming modules and successfully exercising lazy plugin discovery, every
  helper, and request/response imports.

The Windows-only Django SQLite teardown error was resolved by closing the
thread-sensitive async ORM connection before deleting the temporary database.
The process adapter now resolves POSIX process-group functions behind its
existing non-Windows runtime guard, so the standard cross-package MyPy command
also passes on Windows without changing process-termination behavior.

A coordinated candidate containing `jrtc` 3.0.0, the eight sibling
named plugins at 3.0.0, and `jrtc-stream` 0.2.0 passed strict Twine and
archive checks. All ten wheels then installed together in a fresh CPython 3.14
environment; dependency consistency, imports, and all nine
`jrtc.plugins` entry points passed. Nothing was uploaded to PyPI during
verification.

No real Janus Gateway or browser was available. The Janus integration,
full-trickle, load, failure-injection, and security release gates therefore
remain open.

## Historical 0.1.0 construction report

**Workspace version:** 0.1.0  
**Verification date:** 2026-07-11  
**Construction interpreter:** CPython 3.13.5

This report records evidence gathered in the construction environment. It is
not a substitute for the real-system release gates in
`docs/RELEASE_GATES.md`.

## Verified successfully

### Architecture and static checks

- `ruff format --check .`: passed for 77 files.
- `ruff check .`: passed.
- `python scripts/check_boundaries.py`: passed for all nine packages.
- strict MyPy: passed for 33 source files in the framework-neutral core,
  process, FFmpeg, GStreamer, SRS, and Qt packages.
- `python -m compileall -q projects scripts examples`: passed.

The Janus compatibility package and optional Janus bridge are isolated behind
`janus_streaming/_compat.py` and their contract tests. The Django adapter is
validated by real migration/repository tests. They are intentionally not
included in the current strict MyPy command because their upstream/dynamic
framework surfaces require a separately maintained typing policy.

### Tests

The isolated per-project test runner passed **31 tests** across all nine
projects:

| Project | Passed |
|---|---:|
| `stream-orchestrator` | 7 |
| `stream-orchestrator-process` | 2 |
| `stream-orchestrator-ffmpeg` | 2 |
| `stream-orchestrator-gstreamer` | 1 |
| `stream-orchestrator-srs` | 2 |
| `jrtc-stream` | 8 |
| `janus-stream-orchestrator` | 5 |
| `stream-orchestrator-django` | 3 |
| `stream-orchestrator-qt` | 1 |

The test set includes lifecycle idempotency, restart backoff and latching,
mountpoint-loss retargeting, subprocess allowlist security, FFmpeg/GStreamer
profile translation, SRS grants/readiness, Janus request/response contracts,
viewer state/ICE/resume behavior, Janus bridge target validation, Django
migration/CAS/outbox behavior, and Qt async bridging.

### Packaging

- Built nine wheels and nine source distributions.
- Every wheel contains `py.typed`.
- Wheel metadata contains the intended dependency boundaries and Python
  requirements.
- `twine check` passed for all 18 archives.
- `scripts/verify_artifacts.py` passed.

### Clean wheel-install smoke test

The seven Python 3.12+ packages were installed from `dist/` into a fresh Python
3.13 virtual environment and imported successfully:

- `stream-orchestrator`
- `stream-orchestrator-process`
- `stream-orchestrator-ffmpeg`
- `stream-orchestrator-gstreamer`
- `stream-orchestrator-srs`
- `stream-orchestrator-django`
- `stream-orchestrator-qt`

## Janus compatibility validation performed

The exact `janus-api` 2.0.6 wheel was downloaded and inspected. Contract tests
were written against its Streaming request models for:

- RTP, RTSP, and file mountpoint creation;
- `new_is_private` editing;
- empty-list `watch.media` normalization;
- `start` with an answer and resume without a new JSEP;
- individual and completed trickle candidates;
- Janus-level and Streaming-plugin-level errors;
- mountpoint information and dynamically returned RTP ports.

Because `janus-api` 2.0.6 officially requires Python 3.14, the local Python
3.13 construction environment could not execute it unchanged. For contract
execution only, an extracted copy in `/tmp` received a local annotation-
evaluation compatibility adjustment. That temporary copy is **not included in
this workspace or any build artifact**. Consequently, these checks do not
replace a native Python 3.14 run.

## Environment-limited or not yet executed

An attempt to install CPython 3.14.3 with `uv` failed because the environment
could not resolve the GitHub host used by Python Build Standalone. Therefore:

- no `uv.lock` was generated in this environment;
- the two Python 3.14+ packages were not clean-installed under a native Python
  3.14 interpreter here;
- full strict typing against the installed `janus-api` package was not run.

The following production gates also require external systems and remain open:

- real Janus Gateway lifecycle and browser WebRTC tests;
- Janus-to-application unsolicited full-trickle verification;
- real FFmpeg/GStreamer RTP delivery;
- native and bridged RTSP camera failure/recovery;
- OBS/browser publication through SRS;
- distributed locks with fencing and durable worker scheduling;
- load, soak, rolling-restart, network-partition, and failure-injection tests;
- security review, dependency/image scanning, SBOM, and tenant authorization
  testing.

## Commands for the final verification environment

Use Python 3.14 and run:

```bash
uv sync --all-packages --group dev
uv run make verify
```

Then execute the integration, security, and load gates in
`docs/RELEASE_GATES.md` against the exact Janus, SRS, FFmpeg, GStreamer,
browser, database, queue, and deployment versions intended for production.
