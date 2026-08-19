# jrtc-stream

A standalone, typed named-plugin distribution for `janus.plugin.streaming`. It
depends on `jrtc>=3.1,<4`, but **not** on the source orchestrator,
Django, Qt, FFmpeg, GStreamer, or SRS.

The package owns:

- the concrete `StreamingPlugin` subclass, published as the `streaming`
  `jrtc.plugins` entry point;
- strict request models for every Streaming command in
  `janus_streaming.requests` and forward-compatible response models in
  `janus_streaming.responses`;
- typed convenience methods for every Streaming command on `StreamingPlugin`;
- a reusable administrative handle;
- stable mountpoint specifications and response models;
- one-handle-per-viewer negotiation state machines;
- operation deadlines and normalized errors;
- optional runtime helpers for applications that want the package to own a
  `jrtc` session manager.

Core remains named-plugin-free: this package is the sole owner of the Streaming
implementation and never imports
`jrtc.models.streaming` or `jrtc.lib.plugins.streaming`, and never
asks core to provide a registered Streaming implementation. All direct core
imports are confined to `janus_streaming._compat`.

```python
from janus_streaming import StreamingPlugin
from janus_streaming.requests import ListRequest

plugin = await StreamingPlugin(session=session).attach()
response = await plugin.send(ListRequest())
```

Source lifecycle orchestration lives elsewhere. Install
`janus-stream-orchestrator` only when you want to expose this package as a
mountpoint backend to `stream-orchestrator`.
