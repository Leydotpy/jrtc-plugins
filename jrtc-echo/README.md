# jrtc-echo

An independently installable, fully typed client for the Janus EchoTest
plugin. It depends only on `jrtc`; importing it does not install any
other named Janus plugin.

```python
from jrtc.models.base import Jsep
from jrtc_echo import EchoTestPlugin

echo = EchoTestPlugin(session=session)
await echo.attach()
reply = await echo.negotiate(
    Jsep(type="offer", sdp=local_offer),
    audio=True,
    video=True,
    bitrate=1_500_000,
)
remote_answer = reply.jsep
```

`configure()` changes media, recording, bitrate, simulcast, or SVC settings
without renegotiating. `negotiate()` requires an offer and returns the outer
JSEP answer alongside typed plugin data. Plugin and Janus envelope failures are
raised as typed exceptions.

The request schema follows the official
[EchoTest API](https://janus.conf.meetecho.com/docs/echotest.html). Outbound
messages reject undocumented keys; inbound events retain unknown future keys.

