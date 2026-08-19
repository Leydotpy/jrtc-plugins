# stream-orchestrator-srs

SRS-specific components that remain independent of Janus and web frameworks:

- an async HTTP API client;
- a `SourceGate` that holds a stream in `waiting-for-source` until a publisher exists;
- typed publish/unpublish callback parsing;
- short-lived HMAC publish grants for application-level authorization.

The package does not launch FFmpeg or GStreamer. Compose the gate with an
FFmpeg/GStreamer pipeline in the orchestration core. A callback should be
stored idempotently by the host application and then wake its reconciler.
