# jrtc-video

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

The service also lazily attaches one management handle and reuses it for room,
token, moderation, recording, RTP-forwarder, and remote-publisher control
commands. Participant publisher/subscriber handles always remain separate:

```python
from jrtc_video import VideoRoomCreateRequest, VideoRoomService

async with VideoRoomService(session) as rooms:
    await rooms.create_room(VideoRoomCreateRequest(room=1234))
    await rooms.list_participants(1234)  # reuses the same control handle
```

`await rooms.invalidate_management_plugin()` fences the cached control handle
after an application-observed session-loss signal. The next command attaches a
new handle only when the service's session is healthy (and, for generation-aware
JRTC sessions, still belongs to the current generation). `aclose()` waits for an
in-flight management command, detaches the control handle at most once, and is
idempotent. Detach failures are retained in `rooms.metrics` rather than causing
an already-confirmed state-changing command to be retried.

`rooms.metrics` is an immutable snapshot containing attach/reuse/invalidation,
detach, command-failure, and command-duration counters. It contains no SDP, ICE
candidate strings, credentials, or other wire payloads.

Run the deterministic structural benchmark with:

```powershell
uv run python benchmarks/benchmark_management_handles.py --commands 100
```

In a healthy run, the temporary baseline performs 100 attach + 100 command +
100 detach operations, while `VideoRoomService` performs 1 attach + 100 command
+ 1 detach and leaves no management handles attached.

Outbound models serialize only explicitly supplied options. Inbound response
models retain unknown fields for compatibility with newer Janus servers.

Protocol reference: <https://janus.conf.meetecho.com/docs/videoroom.html>
