# Operational model

## Recommended service split

For production-scale deployments, keep web request workers, orchestration
workers, media workers, Janus, and SRS as separately supervised components.
Django should persist intent and expose authenticated commands. Reconcilers own
long-running convergence. Media workers own FFmpeg/GStreamer processes.

## Reconciliation

Use event-triggered reconciliation for responsiveness and periodic
reconciliation for correctness. Every operation must be idempotent or followed
by observation. A lost response after remote success must not create duplicate
mountpoints or producers.

## Locks and fencing

The included in-memory lock is only process-local. Distributed deployments need
a durable lock implementation with fencing tokens and repository writes that
reject stale holders. Do not assume a Redis lock without fencing is sufficient.

## Health

Track separately:

- controller/reconciler liveness;
- Janus session/control health;
- mountpoint existence and configuration;
- source process/publisher health;
- per-track packet freshness;
- optional synthetic WebRTC viewer probes.

## Restart behavior

The core applies bounded exponential backoff with jitter. Clean process exit is
not a failure under `on-failure`. Exhausted failures and clean end-of-stream are
latched until a new explicit start request resets the terminal state.

## Shutdown

Disable mountpoints before stopping sources. Drain viewers when policy allows,
then kick remaining viewers, stop producers, destroy mountpoints, and only then
release ports/capacity. Cleanup must be idempotent and cancellation-safe.

## Metrics

Use low-cardinality labels: operation, driver, backend, outcome, and node class.
Keep stream IDs, user IDs, mountpoint IDs, and source URLs in structured logs or
traces rather than metric labels.
