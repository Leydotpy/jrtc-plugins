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
- `uv build`: source distribution and wheel built; final artifact validation follows
  the completed source checkout and consumer installation.
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
