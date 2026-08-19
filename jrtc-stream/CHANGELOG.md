# Changelog

## 0.2.0 - 2026-07-12

- Migrated `jrtc-stream` to `jrtc>=3.1,<4`.
- Moved all Streaming request/response models into `janus_streaming.requests`
  and `janus_streaming.responses`.
- Added the extension-owned `StreamingPlugin` class and the `streaming`
  `jrtc.plugins` entry point, including typed helpers for every command.
- Removed the dependency on `jrtc.models.streaming` and on a
  core-registered Streaming class.
- Corrected end-of-candidates serialization to `{"completed": true}`.
- Redacted admin keys, mountpoint/camera credentials, SDP, and ICE candidate
  values from default object representations.
- Strengthened dependency-boundary checks for the core package range,
  entry-point metadata, and model ownership.
- Made the complete Windows verification suite pass by closing Django's
  thread-sensitive SQLite connection during teardown and isolating POSIX
  process-group symbols behind their existing runtime guard.
- Replaced stale mixed artifacts with publication-safe `--no-sources` builds,
  strict artifact hygiene and Twine checks, SHA-256 manifests, and an SPDX 2.3
  SBOM.

## 0.1.0 - 2026-07-11

- Initial modular workspace.
- Standalone Janus Streaming administration/viewer client.
- Framework-neutral orchestration core.
- Optional Janus bridge.
- Independent process, FFmpeg, GStreamer, SRS, Django, and Qt packages.
- Tests, boundary enforcement, build tooling, architecture/security/operations
  documentation, and Codex review instructions.
