# jrtc-room

Independent, typed bindings for the Janus VideoRoom SFU plugin. It depends on
`jrtc>=3.1,<4` and does not install any other named Janus plugin.

```python
from jrtc_video import (
    PublisherJoinRequest,
    SubscribeTarget,
    SubscriberJoinRequest,
    VideoRoomPlugin,
)

async with VideoRoomPlugin(session=session) as publisher:
    joined = await publisher.join_publisher(PublisherJoinRequest(room=1234))

async with VideoRoomPlugin(session=session) as subscriber:
    attached = await subscriber.join_subscriber(
        SubscriberJoinRequest(
            room=1234,
            streams=[SubscribeTarget(feed=42, mid="1")],
        )
    )
```

`VideoRoomService` safely owns related publisher and subscriber handles for an
application lifecycle. It is async-only, scoped to one session, and never
creates a hidden global event loop or thread:

```python
from jrtc_video import VideoRoomService

async with VideoRoomService(session) as rooms:
    publisher = await rooms.publisher(room=1234, participant=7, display="Ada")
    subscriber = await rooms.subscriber(
        room=1234,
        owner=7,
        key="stage",
        streams=[SubscribeTarget(feed=42)],
    )
```

Outbound models serialize only explicitly supplied options. Inbound response
models retain unknown fields for compatibility with newer Janus servers.

Protocol reference: <https://janus.conf.meetecho.com/docs/videoroom.html>
