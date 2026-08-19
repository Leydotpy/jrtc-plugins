# Release gates

A package may be published only after its own independent build and tests pass.
The complete solution may be described as production-ready only after all
applicable gates pass.

## Automated

- formatting and Ruff clean;
- strict type checks for supported packages;
- dependency-boundary script clean;
- unit and contract tests clean;
- wheel and sdist build clean;
- clean-environment installation test;
- package import smoke tests;
- dependency vulnerability and license scan;
- generated artifacts contain no credentials or local paths.

## Integration

- real Janus session, attach, create, info, enable, disable, destroy;
- browser watch/offer/answer/ICE/media/stop;
- RTP from FFmpeg and GStreamer;
- native and bridged RTSP camera loss/reconnect;
- SRS browser and OBS publish/unpublish;
- process crash, input stall, Janus restart, SRS restart;
- two reconcilers contending for one stream;
- web/worker rolling restart and graceful shutdown;
- load tests for source count, packet rate, viewers, and control concurrency.

## Security

- SSRF controls and media-probe isolation;
- command/profile injection tests;
- secret redaction tests;
- authorization and tenant-isolation tests;
- callback authentication/replay tests;
- RTP/network policy review;
- dependency/image/SBOM review.
