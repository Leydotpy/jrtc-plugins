# Composition guide

## Local FFmpeg plus Janus

Create and start a `jrtc` session, then compose:

1. `StreamingRuntime` from `jrtc-stream`;
2. `JanusStreamingMountpointBackend` from `janus-stream-orchestrator`;
3. `LocalProcessExecutor`;
4. an FFmpeg driver from `make_ffmpeg_driver`;
5. repository, locks, events, controller, and service from the core.

The application owns startup and shutdown order:

```text
start Janus manager/session
start StreamingRuntime/admin handle
start process executor/orchestrator workers
accept application traffic

stop accepting commands
stop reconciler
request/complete source shutdown
close process executor
close StreamingRuntime
stop Janus manager/session
```

## SRS plus FFmpeg or GStreamer

Register `SrsPublisherGate` for source kind `srs-publisher`. Register either the
FFmpeg or GStreamer driver for the pipeline. The gate waits for publication;
the selected driver bridges the published stream to the mountpoint targets.
SRS never needs to import the encoder package.

## Native Janus RTSP

Use:

```text
source.kind = "rtsp"
pipeline.driver = "janus-native-rtsp"
```

Register `NativeRtspSourceDriver` and use the Janus mountpoint backend. Janus
owns the RTSP pull; the no-process driver represents that ownership while media
readiness remains based on Janus observations.

## Django

Use `DjangoStreamRepository` and `DjangoEventPublisher`, but construct the
controller and selected drivers in the Django project, not in the reusable
Django package. Start network resources from ASGI lifespan or a dedicated
worker process. Do not perform network I/O in `AppConfig.ready()`.

## Qt

Use the core directly in an asyncio-capable desktop application, or use
`CallbackOrchestratorBridge` to run it on a dedicated loop thread. Install the
PySide6/PyQt6 optional extra only in the GUI project. For central deployments,
prefer a remote orchestration API so desktop clients do not receive Janus/SRS
administrative credentials.
