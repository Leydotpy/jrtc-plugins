# jrtc-call

Typed, independently installable bindings for `janus.plugin.videocall`. The
package depends on `jrtc` and does not pull in unrelated Janus plugin
implementations.

```python
from jrtc.models.base import Jsep
from jrtc_call import VideoCallPlugin

phone = VideoCallPlugin(session=session)
await phone.attach()
await phone.register("alice")
calling = await phone.call("bob", Jsep(type="offer", sdp=offer_sdp))
```

All six documented operations (`list`, `register`, `call`, `accept`, `set`,
and `hangup`) are asynchronous. `call` requires an offer, `accept` requires an
answer, and `set` optionally carries an offer or answer for renegotiation.
Detach the handle to release its username; Janus has no `unregister` request.

Models follow the official
[VideoCall API](https://janus.conf.meetecho.com/docs/videocall.html). Outbound
payloads reject unknown keys, while inbound events retain additions made by a
future Janus release.

