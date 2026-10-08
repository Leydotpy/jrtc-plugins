# Implementation evidence — 2026-10-08

Runtime change: VideoRoomService now owns one shielded cleanup task, with a finite
15-second configurable attempt budget. Caller cancellation stays visible while
cleanup continues. Incomplete cleanup remains closing and retryable instead of
being marked closed. Concurrent callers share cleanup; new commands cannot reopen
it. Metrics record cleanup failures/timeouts. Version 3.0.3 is prepared; no package
has been published.

## Verification

Python 3.12.14 with the actual JRTC source and pinned Broka/Dispio dependencies:

- `PYTHONPATH=src:../../jrtc/src python -m pytest tests`: 33 passed.
- New regressions cover caller cancellation while a management command owns its
  lock, during attach/detach, timeout-and-retry, and pending publisher provisioning.
- `uv build`: source distribution and wheel built; the final wheel includes the license/type markers. The
  frozen Synq consumer built and imported the pinned Git artifact successfully.
- `PYTHONPATH=src:../../jrtc/src python benchmarks/benchmark_management_handles.py
  --commands 100`: persistent path attached once, sent 100 commands and detached
  once, with zero handles remaining. Temporary path attached/detached 100 times.
  Raw synthetic timings are in `evidence/implementation-management-benchmark.json`.

## Integration and rollback

A service belongs to one actual session object. Synq's adapter integration must
close it before manager/session teardown and create a new one after replacement.
Live Janus latency, mixed workload load tests and published artifacts remain
pending; these are not certified by fake-session request counts. Timeouts during
detach leave the remote result unknown; session teardown owns eventual cleanup.
Revert the implementation commits and restore the tested dependency lock to roll
back. No sibling plugin, deployment or merge was changed.

Code commit: `c91c9ada66076041b8890c7c971ce9d4792b750a`. Base: `26fe283c2f65e745da03359c514a18361313adf4`.

## Consumer verification completed — 2026-10-08

Synq's frozen consumer install built the exact reviewed Git commits and imported
JRTC 3.2.0 and jrtc-video 3.0.3 from site-packages on Python 3.14.8/Django 6.0.7
with Broka 0.0.2 and Dispio 0.0.2. It passed the required contracts/new regressions
and the real ORM/registry/service integration checks; see Synq's IMPLEMENTATION.md
for the full suite's seven pre-existing missing-startup-file failures.

The installed VideoRoom model/service suite also passed all 33 unittest tests in
that consumer environment. Synq tests prove service reuse, replacement with a
recycled integer ID, and cleanup-before-manager ordering despite repeated caller
cancellation. Core observer callbacks remain separate from manager recovery.

Local wheel SHA-256 values (build provenance, not published registry hashes):

- jrtc-3.2.0: `3e0b82c7edba0c8de20f98fa53af7de9a5cb29c0bef880717d6a6c44faf2d7e8`
- jrtc_video-3.0.3: `041689387e20cf72901aef472c5b874444058cf6504650ba41113353584f2a13`

Review PRs: [Synq #2](https://github.com/Leydotpy/synq/pull/2), [synq.js #7](https://github.com/Leydotpy/synq.js/pull/7), [JRTC #2](https://github.com/Leydotpy/jrtc/pull/2), [VideoRoom #2](https://github.com/Leydotpy/jrtc-plugins/pull/2).
No published-release or live media acceptance is claimed.

The root pyproject.toml obsolete ../main/v3.1 source override was removed in commit 87bbb9b79870724a91fc98f8711c55f5cb4519e2. It otherwise broke uv installation of the VideoRoom Git subdirectory. No sibling plugin implementation changed. V-T02 is now ready for review; V-T03 remains blocked on live measurements.
