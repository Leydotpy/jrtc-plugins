# AGENTS.md — jrtc-video

## Scope and reading order

This file governs work in jrtc-video only. The current task is an evidence-backed refinement of the supplied requirements. These instructions do not assert that the requested application work is already complete.

1. Read [the audit](docs/agent-audit/README.md) and its pinned source baseline.
2. Select the relevant concern in [WORK_PLAN.md](docs/agent-audit/WORK_PLAN.md); inspect the current code before editing.
3. Read the affected numbered sections of [source-requirements.md](docs/agent-audit/source-requirements.md) and the [shared contract](docs/agent-audit/CROSS_REPO_CONTRACT.md). The original brief is preserved for traceability. Non-conflicting requirements remain applicable; the explicit decisions below supersede obsolete or ambiguous wording.
4. Update [progress.json](docs/agent-audit/progress.json) and the matching [requirements.csv](docs/agent-audit/requirements.csv) with evidence, not estimates.

Audited target: `Leydotpy/jrtc-plugins` at `main`, commit `bec03a533ab3af33c1deef822e8249f123a007dc`. Work from the requested branch/current authorized successor; never silently switch to the default branch. Evidence for an older commit must be rechecked before marking a current task complete.

## Current decisions and stronger acceptance rules

- This AGENTS file applies only to jrtc-video. Do not modify sibling plugins as a side effect of this audit.
- The reusable service is implemented; preserve it and its typed commands. Historical wording saying management handles are currently temporary describes the pre-upgrade baseline, not a request to revert current code.
- One VideoRoomService owns one actual Janus session object. The application must create a new service when the manager supplies a different session; session is not a replaceable public property. Same-object generation changes must still invalidate cached handles.
- Treat close cancellation as a lifecycle operation, not just a normal exception. Setting _closed in a finally block while cleanup has not run is not successful shutdown. Use an owned, bounded cleanup operation or retryable incomplete state; repeated close must finish outstanding cleanup and callers must still observe cancellation.
- Closing must block new management creation before waiting for in-flight commands. Never detach a healthy handle underneath an active command. Capture and test cancellation at lock acquisition, attach, command, detach and participant provisioning boundaries.
- A timeout/cancellation after sending a state-changing command means the remote outcome may be unknown. Do not replay automatically, and do not confuse a later cleanup failure with command failure. Preserve typed domain versus lifecycle errors.
- Retain whole-sequence ICE delegation, explicit completion and dedicated participant handles. Do not move browser batching, Synq authorization or database ownership into this package.
- Bound service shutdown and document ownership of the budget. Report cleanup failures with metadata and counters; no SDP, candidate strings or credentials. Measure serialization/lock contention before changing the safe command serialization model.

## Reviewable execution

- Work on a separate branch. Keep one concern and its necessary regression checks reviewable in each commit/PR; preserve unrelated changes.
- Follow the user-authorized scope. This audit does not pre-authorize future runtime changes. For later implementation, the user can select one concern, several concerns or the whole plan; do not add redundant permission gates for work already authorized. Do not merge/deploy unless authorized.
- If the user selects one concern, report its result and pause before starting another. Hand back changed paths, behavioral effect, exact verification commands/results, known limitations, dependency effects and rollback steps.
- Use task states `not_started`, `in_progress`, `blocked`, `ready_for_review`, `accepted`. Only the user/maintainer accepts work. A passing unit test or merged documentation is not implementation completion.
- Keep implementation state (`present`, `partial`, `missing`, `policy`, `deferred`) separate from verification state (`source_review`, `runtime_subset_passed`, `reproduced_gap`, `external_not_verified`). New instructions stay pending until code and the relevant acceptance evidence exist.
- Preserve source section IDs; add improvement IDs instead of silently deleting requirements. Record blockers explicitly. Unavailable infrastructure is a verification limitation, not a pass or a code failure.
- Use deterministic barriers/fake clocks for lifecycle races. Do not replace meaningful assertions with source-string matching or fake external dependencies merely to make a suite pass.
- Never include tokens, credentials, auth payloads, full SDP or raw ICE addresses in audit artifacts, commits or routine logs.

## Verification commands

Run from the repository root with the declared runtime/dependencies and required services:

```sh
cd jrtc-video
uv run --extra test python -m pytest tests
uv run python benchmarks/benchmark_management_handles.py --commands 100
```

These are required follow-up gates, not claims that they passed in this audit. See the audit for what actually ran. A final completion report must include cross-repository compatibility and any live checks required by the selected concern.
