# jrtc-video — concern-by-concern work plan

The audit/instruction change is ready for review. The implementation tasks below are **not started by this documentation change**. Existing code is credited in requirements.csv; tasks describe the remaining corrections or verification, not a request to repeat completed features.

Task IDs are unique across the four repositories: S=Synq, F=frontend, C=core, V=VideoRoom. A dependency in another repository refers to that repository's WORK_PLAN.md. Dependencies gate integration/release; isolated test preparation may proceed earlier. No task requires automatic delegation to other agents.

| Task | Priority | Dependencies | State |
| --- | --- | --- | --- |
| V-T01 — Make service close cancellation-safe | P1 | None | not_started |
| V-T02 — Verify lifecycle integration and release API | P1 | V-T01 | not_started |
| V-T03 — Record structural and live performance evidence | P2 | V-T01, V-T02 | not_started |

## V-T01 — Make service close cancellation-safe

**Scope:** VideoRoomService.aclose; lifecycle tests.

**Acceptance:** Cancel close while a management command owns the lock, during attach, during detach and while participant creation is pending. Do not publish closed=True until owned cleanup is completed or a bounded cleanup owner can finish it. A repeated close must complete remaining cleanup. Preserve CancelledError to callers, prevent reopen/duplicate detach, bound teardown and never replay a confirmed state-changing command.

**Review evidence:** exact code commit, affected requirement IDs, regression results, external checks/limitations and rollback instructions. Set ready_for_review only after the selected scope is concrete; accepted requires maintainer review.

## V-T02 — Verify lifecycle integration and release API

**Scope:** package tests/docs; Synq adapter integration.

**Acceptance:** Run model/service tests with the selected JRTC wheel. Prove same session reuse and separate publisher/subscriber roles; replacement session gets a new service, never an adopted stale ID. Document fixed-session ownership and supported package release bounds. Verify Synq closes management services before destroying sessions.

**Review evidence:** exact code commit, affected requirement IDs, regression results, external checks/limitations and rollback instructions. Set ready_for_review only after the selected scope is concrete; accepted requires maintainer review.

## V-T03 — Record structural and live performance evidence

**Scope:** management benchmark; exact Janus deployment.

**Acceptance:** Run 100 list-participant commands and mixed management commands; record attach/command/detach counts, p50/p95, CPU and residual handles including cancellation/recovery. Distinguish fake-session request-count assertions from live latency. Confirm concurrent command serialization is acceptable before changing lock granularity.

**Review evidence:** exact code commit, affected requirement IDs, regression results, external checks/limitations and rollback instructions. Set ready_for_review only after the selected scope is concrete; accepted requires maintainer review.

## Updating the tracker

When starting, set only the selected task to in_progress and record its branch. Record blocked reasons when a real dependency prevents progress. On completion, add implementation_commit and verification_evidence with commands, runtime/version, observed results and evidence paths; update the relevant requirement rows. Preserve this audit baseline, add a dated assessment for a new head, and never overwrite historical evidence as if it were obtained at the new commit. For a docs-only change, leave application task states unchanged.
