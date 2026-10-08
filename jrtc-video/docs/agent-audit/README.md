# jrtc-video — AGENTS implementation audit

**2026-10-08 implementation follow-up:** runtime changes are now proposed in the coordinated draft PRs. Read [IMPLEMENTATION.md](IMPLEMENTATION.md) and the updated work plan for current evidence and external gates. The audit below is the preserved 2026-10-07 baseline.

Audit date: 2026-10-07. **Substantially implemented but not complete. Reusable typed management handles, concurrency locks, invalidation and metrics exist. Cancellation during aclose can mark the service closed while leaving its management plugin cached, and a repeated close then skips cleanup.**

This PR improves instructions and adds an evidence/tracking pack. It does **not** change runtime application code, fix the listed defects, or declare the remaining implementation tasks complete. Review and merge the instruction update independently; select implementation concerns from WORK_PLAN.md afterward.

## Audited baselines

| Repository scope | Requested branch | Audited commit |
| --- | --- | --- |
| Synq backend | `v4` | `2d8682701300f27ab3771e9ea72413b3f7631a49` |
| Synq browser client | `codex/batched-ice-meeting-sounds` | `da471c92989ccf28a26de14d6ec4d1356c647bed` |
| JRTC core | `main` | `de64c1e02b550049c8253fdef7d47a87b765c9e8` |
| jrtc-video | `main` | `bec03a533ab3af33c1deef822e8249f123a007dc` |

The branch heads were rechecked and unchanged before preparing this update. All code evidence links are pinned to the audited commits. The attached standalone AGENTS.md duplicates AGENTS(5).md and is not an additional scope. Uploaded package metadata was treated as supporting context; repository source at the requested refs is authoritative for implementation status. Secret material was excluded from retrieval and commits.

The four repository trees were inspected, and 302 relevant source, test, configuration and documentation files were retrieved initially (plus the frontend provider/layout follow-up). Generated/vendor snapshots and unrelated plugins are outside the implementation scope. This is a requirement-focused code audit, not a claim that every line of every repository received a security review.

## Meaning of the statuses

- **present**: relevant implementation found; verification is reported separately.
- **partial**: some implementation exists, but a defect, omitted behavior or acceptance evidence remains.
- **missing**: required implementation was not found or the current path still implements the superseded behavior.
- **policy**: ownership/rollout constraint, not a standalone feature completion.
- **deferred**: the original brief explicitly postpones the work.

source_review means code/tests were inspected. runtime_subset_passed covers only the named executed subset. reproduced_gap records a controlled observation of a defect. external_not_verified means required live/deployment evidence is absent. No completion percentage is manufactured from these categories.

## Requirement coverage

Every numbered section in the supplied file is mapped in [requirements.csv](requirements.csv), with stable section IDs, separate implementation/verification status, findings and pinned evidence links. Rows share a group assessment where the same code serves several requirements; the CSV does not imply that every sub-bullet has an individual passing test. Unnumbered mission/order/definition-of-done text is assessed by this verdict and the work plan.

| Group | Original sections | Concern | Implementation | Verification |
| --- | --- | --- | --- | --- |
| V01 | 0, 1, 2, 12, 15 | Typed package scope and ownership | present | source_review |
| V02 | 3, 4, 5, 16, 17 | Lazy management reuse and concurrent first use | present | source_review |
| V03 | 6, 13, 20 | Participant separation and delegated ICE | present | source_review |
| V04 | 7, 9 | Deterministic close and invalidation races | partial | reproduced_gap |
| V05 | 8, 11, 18, 19 | Session loss and error classification | present | source_review |
| V06 | 10 | No replay of confirmed commands after cleanup failure | present | source_review |
| V07 | 14 | Application integration API | present | source_review |
| V08 | 21 | Low-cost lifecycle metrics | present | source_review |
| V09 | 22 | Management request-count benchmark | partial | external_not_verified |

## Principal findings

The cancellation reproduction holds the service management lock, starts aclose, cancels it while waiting, releases the lock, then calls aclose again. The observed state is closed=True with the cached management plugin still present. This is a local lifecycle leak/stuck-cleanup condition; it does not establish how long a remote handle would survive on a real Janus deployment. The revised instructions require cancellation-specific regression coverage and bounded retryable/owned cleanup.

Synq's missing use of this package service is tracked under S07/S-T04, not counted as a missing package API. A VideoRoomService is tied to one session object; replacement needs a new service.

### V01 — Typed package scope and ownership

VideoRoom-specific typed API and application-independent service remain separate from Django and core; services are scoped instances, not a global singleton.

Evidence: [plugin.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/plugin.py); [models.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/models.py); [service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/service.py).

### V02 — Lazy management reuse and concurrent first use

A management lock serializes lazy attach/commands, a whitelist excludes participant methods, and focused tests assert one attach/reuse.

Evidence: [service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/service.py#L500); [service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/service.py#L592); [test_plugin_service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/tests/test_plugin_service.py#L201).

### V03 — Participant separation and delegated ICE

Publisher/subscriber wrappers retain dedicated handles and forward whole candidate sequences to generic JRTC. Tests check separation and one ordered non-waiting ICE request.

Evidence: [service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/service.py#L144); [service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/service.py#L249); [test_plugin_service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/tests/test_plugin_service.py#L156).

### V04 — Deterministic close and invalidation races

Normal close is locked/idempotent, but cancellation while awaiting _management_lock enters finally and sets _closed=True before cleanup. The management reference remains and the next aclose returns immediately. Existing close tests do not cover this cancellation.

Evidence: [service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/service.py#L1065); [test_plugin_service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/tests/test_plugin_service.py#L217).

### V05 — Session loss and error classification

Session/generation/registry checks invalidate stale management plugins; domain errors normally retain them. Tests cover generation changes and transport/domain errors. Replacement of the actual session object requires a new service owned by the application.

Evidence: [service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/service.py#L424); [service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/service.py#L546); [test_plugin_service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/tests/test_plugin_service.py#L234).

### V06 — No replay of confirmed commands after cleanup failure

Management cleanup failures are counted without replacing a successful result or retrying the command. A focused test verifies this rule.

Evidence: [service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/service.py#L447); [test_plugin_service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/tests/test_plugin_service.py#L290).

### V07 — Application integration API

VideoRoomService exposes typed helpers, management_command, invalidation, metrics and aclose. Synq consumption is separately missing and must not be confused with package API absence.

Evidence: [__init__.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/__init__.py); [README.md](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/README.md); [service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/service.py).

### V08 — Low-cost lifecycle metrics

Immutable metrics snapshots include attaches, reuse, invalidation, detach failures, command duration and error categories.

Evidence: [service.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/src/jrtc_video/service.py#L97).

### V09 — Management request-count benchmark

The deterministic benchmark compares temporary versus persistent fake sessions and asserts 1 attach/N commands/1 detach/zero residual handles. It was not executed here and is not live Janus latency evidence.

Evidence: [benchmark_management_handles.py](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/benchmarks/benchmark_management_handles.py); [README.md](https://github.com/Leydotpy/jrtc-plugins/blob/bec03a533ab3af33c1deef822e8249f123a007dc/jrtc-video/README.md).

## Verification actually performed

The package tests and fake-session benchmark were inspected but not run because the required JRTC/Broka/logvista/pytest environment was unavailable. A focused AST extraction executed the actual service aclose method with a held management lock, cancelled it, and confirmed closed=True with the cached plugin still present after a second close. It does not simulate a live Janus server.

Focused cancellation reproduction: [script](evidence/reproduce_video.py), [output](evidence/video-reproductions.txt). From the monorepo root run `python jrtc-video/docs/agent-audit/evidence/reproduce_video.py`. This executes the extracted source method with controlled locks and state, not a substituted implementation. Its zero exit code only means the reproduction ran; the reported leaked cached reference is the failure.

The GitHub check-runs endpoint returned zero checks for each audited SHA at inspection time. This is not evidence that tests failed or passed; no CI result is claimed. No live Janus, external broker, production database or browser session was exercised. Source assertions and prior repository benchmark prose are not substitutes for those checks.

## Improvements implemented in the instructions

1. A concise root policy replaces ambiguous baseline-as-current wording and records exact repository ownership, branch and precedence.
2. The original supplied requirements are preserved, hashed in progress.json and mapped section-by-section; Synq's earlier migration safety requirements are retained separately.
3. Shared ICE, event identity, lifecycle and release ordering are explicit, including the backend/frontend compatibility blocker.
4. Cancellation, stale async continuations, failure outcomes, queue/byte budgets, notification persistence and real package API checks are turned into concrete acceptance work.
5. Concern IDs, dependencies and review states let the user inspect one job at a time without incorrectly marking documentation or code inspection as implementation success.
6. Verification commands, limits and reproducible observations make claims reviewable; dependency/runtime blockers remain visible.

Read [WORK_PLAN.md](WORK_PLAN.md) for the implementation order and [progress.json](progress.json) for the current task states. The source brief remains in [source-requirements.md](source-requirements.md); proposed stronger behavior is governed by the root decisions and [shared contract](CROSS_REPO_CONTRACT.md).
