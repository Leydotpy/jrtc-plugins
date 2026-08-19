# Known limitations of this generated workspace

- Real Janus, SRS, FFmpeg, GStreamer, RTSP camera, browser, and network tests
  were not available in the construction environment.
- The core includes process-local memory repository/locks/events for testing and
  desktop use; a distributed deployment still needs fenced locks and durable
  worker scheduling.
- The Django adapter supplies persistence and lifecycle primitives, not a
  preselected REST/WebSocket API, authentication policy, task queue, or worker.
- The Qt adapter supplies event-loop/callback plumbing, not application screens.
- The local process executor cannot recover ownership of an orphan process after
  its Python host exits; use containers, Kubernetes, or a remote media agent for
  durable production supervision.
- SRS HMAC grants require enforcement by the host reverse proxy or callback
  service; token generation alone does not secure publishing.
- Dynamic Janus RTP creation does not infer an RTCP target when Janus does not
  return one.
- Full inbound trickle behavior must be verified against the exact `jrtc`
  transport implementation.
