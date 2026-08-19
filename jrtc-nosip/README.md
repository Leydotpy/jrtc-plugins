# jrtc-nosip

Typed async bindings for `janus.plugin.nosip`, packaged separately from
`jrtc` and every other named plugin.

NoSIP bridges WebRTC media to plain RTP while the application owns external
signalling. The API therefore makes the two SDP directions explicit:

```python
from jrtc.models.base import Jsep
from jrtc_nosip import NoSipPlugin

bridge = NoSipPlugin(session=session)
await bridge.attach()

# WebRTC JSEP -> bare SDP for an external signalling protocol.
generated = await bridge.generate(Jsep(type="offer", sdp=webrtc_offer))
plain_sdp = generated.data.result.sdp

# Bare remote SDP -> JSEP returned in processed.jsep.
processed = await bridge.process("answer", remote_plain_sdp)
remote_jsep = processed.jsep
```

The package covers `generate`, `process`, `hangup`, `recording`, `keyframe`,
`rtp_forward`, `stop_rtp_forward`, and `listforwarders`. Ports, payload types,
stream collections, JSEP directions, and SRTP parameter pairs are validated
before I/O.

See the official [NoSIP API](https://janus.conf.meetecho.com/docs/nosip.html).
Outbound schemas are strict; inbound schemas retain unknown keys and event
variants for compatibility with newer Janus versions.

