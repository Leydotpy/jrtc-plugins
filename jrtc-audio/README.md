# jrtc-audio

Typed, async bindings for the Janus AudioBridge plugin. The distribution is
independent from other named Janus plugins and depends only on
`jrtc>=3.1,<4`.

```python
from jrtc_audio import AudioBridgeJoinRequest, AudioBridgePlugin
from jrtc.models.base import Jsep

async with AudioBridgePlugin(session=session) as bridge:
    await bridge.join(AudioBridgeJoinRequest(room=1234))
    reply = await bridge.configure(
        jsep=Jsep(type="offer", sdp=local_offer),
    )
    answer = reply.jsep
```

The reverse offer/answer flow is supported without changing negotiation roles:

```python
async with AudioBridgePlugin(session=session) as bridge:
    offered = await bridge.request_offer(room=1234)
    await bridge.answer_offer(Jsep(type="answer", sdp=local_answer))
```

Plain-RTP injection is represented by `AudioBridgeRtpTransport()`: an empty
object intentionally means send-only. Supplying only one of `ip` and `port` is
rejected before a malformed request reaches Janus.

All outbound models reject unknown fields and serialize only values explicitly
provided by the caller. Inbound models retain unknown fields so a newer Janus
server can add response metadata without breaking this client.

Protocol reference: <https://janus.conf.meetecho.com/docs/audiobridge.html>
