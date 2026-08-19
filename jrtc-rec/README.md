# jrtc-rec

Typed, independently installable bindings for `janus.plugin.recordplay`. This
distribution depends on `jrtc` and no other named Janus plugin.

```python
from jrtc.models.base import Jsep
from jrtc_rec import RecordPlayPlugin

media = RecordPlayPlugin(session=session)
await media.attach()

# Recording: the browser offers and Janus answers.
recording = await media.record("demo", Jsep(type="offer", sdp=offer_sdp))

# Playback: Janus offers first, then the browser answers.
preparing = await media.play(recording_id=1234)
await media.start(Jsep(type="answer", sdp=answer_sdp))
```

The client deliberately encodes the asymmetric JSEP state machine: `record`
requires an offer, `play` rejects JSEP entirely, and `start` requires an
answer. It also preserves Janus's synchronous/asynchronous split: `list`,
`update`, and `configure` wait for immediate plugin data; media-state requests
wait for their event.

The schemas include the current `update` recording and `restart` playback
options in Janus, plus the exact hyphenated wire keys used by `configure`.
See the official [Record&Play API](https://janus.conf.meetecho.com/docs/recordplay.html)
and [recordings format](https://janus.conf.meetecho.com/docs/recordings.html).

