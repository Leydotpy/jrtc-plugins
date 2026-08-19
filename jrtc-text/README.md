# jrtc-text

Typed bindings for `janus.plugin.textroom`, packaged independently from
`jrtc` and other named plugins.

TextRoom has two intentionally separate protocols:

- Janus plugin messages establish/restart the data-only PeerConnection and
  perform synchronous room administration using a `request` field.
- Chat participation travels as UTF-8 JSON over a DataChannel using a
  `textroom` field and a mandatory transaction.

```python
from jrtc.models.base import Jsep
from jrtc_text import TextRoomPlugin

textroom = TextRoomPlugin(session=session)
await textroom.attach()
offer = await textroom.setup()
# Apply offer.jsep in the WebRTC implementation, create the data channel,
# then return the local answer.
await textroom.ack(Jsep(type="answer", sdp=answer_sdp))

textroom.bind_datachannel(channel)
await textroom.join(1234, "alice", display="Alice")
await textroom.message(1234, "Hello everyone")
```

Room administration is deliberately independent of the WebRTC transport:

```python
await textroom.create_room(
    room=1234,
    description="Support",
    secret="room-admin-secret",
    history=50,
)
rooms = await textroom.list_rooms()
participants = await textroom.list_participants(1234)
```

`DataChannelLike` is a small adapter protocol (`ready_state` plus `send`).
Incoming channel payloads must be handed to `feed_datachannel()`. The
transaction manager bounds pending requests, event backlog, and payload size;
it applies per-request timeouts and deterministically fails pending futures
when closed or cancelled. It does not close the application's underlying
WebRTC transport. Feed each incoming UTF-8 frame back to
`textroom.feed_datachannel(payload)` on the channel's owning event loop.

Room list/create/edit/destroy/exists/ACL queries use Janus messages. Join,
message, announcement, leave, and kick use the DataChannel and can never be
accidentally serialized into the Janus plugin body.

All operations accept a per-call timeout. Applications should call
`await textroom.aclose()` during shutdown so outstanding transaction waiters
are failed deterministically before the Janus handle is detached.

See the official
[TextRoom API](https://janus.conf.meetecho.com/docs/textroom.html).
