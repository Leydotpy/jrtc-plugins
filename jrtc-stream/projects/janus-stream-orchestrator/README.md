# janus-stream-orchestrator

A deliberately thin integration bridge. It adapts the framework-neutral
`stream-orchestrator` ports to the standalone `jrtc-stream` client.
Neither upstream package depends on this project.

## Responsibilities

- translate stream track contracts to Janus RTP mountpoints;
- create native Janus RTSP mountpoints when explicitly selected;
- expose Janus mountpoint observations to the reconciler;
- keep management and RTSP credentials behind application-supplied resolvers;
- provide the no-process `janus-native-rtsp` source driver.

This package does not import Django, Qt, FFmpeg, GStreamer, or SRS.
