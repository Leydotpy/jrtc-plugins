# Upstream compatibility

## `jrtc`

`jrtc-stream` targets `jrtc>=3.1,<4` and Python 3.14+.
All direct imports from `jrtc` are isolated in `janus_streaming/_compat.py`.
The distribution owns its Streaming request/response models, convenience
helpers, and concrete `StreamingPlugin`; core supplies only the plugin-agnostic
handle and transport envelopes. The class is discoverable as the `streaming` entry in the
`jrtc.plugins` entry-point group.

When widening the dependency range:

1. download and inspect the new wheel/source;
2. diff the generic plugin attach/send/trickle/detach contract;
3. validate the entry-point loader against an independently built wheel;
4. compare every owned request/response model and helper with the targeted
   Janus documentation;
5. run contract tests for every command;
6. run real Janus integration tests;
7. test session loss, late responses, detach, and trickle ICE;
8. update the compatibility matrix and changelog.

Do not add a direct `jrtc` import anywhere else or restore an import from
`jrtc.models.streaming` or `jrtc.lib.plugins.streaming`.

## Janus Streaming

The bridge recognizes Streaming error code 455 as a missing mountpoint. Verify
error constants against the targeted Janus source on upgrades. Dynamic RTP
creation returns RTP target ports; RTCP availability must be explicitly
validated/configured for workflows that require RTCP feedback.

## Full trickle

Browser-to-Janus trickle is represented. Before claiming full-trickle support,
verify Janus-to-application unsolicited trickle dispatch through the exact
`jrtc` version and a real browser test. Do not mask a transport-level gap
inside the orchestration bridge.

## SRS

Treat callbacks as notifications, not authoritative state. Reconfirm callback
payloads, API response fields, WHIP endpoint behavior, and authorization design
against the deployed SRS version.

## FFmpeg/GStreamer

Profiles are deployment contracts, not universal guarantees. Validate codecs,
payload types, H.264 profile/packetization, keyframe cadence, timestamps, RTCP,
and browser interoperability on every supported build/image.
