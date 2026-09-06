"""Public API for the independently installable VideoRoom client."""

from .errors import (
    VideoRoomError as VideoRoomError,
)
from .errors import (
    VideoRoomJanusError as VideoRoomJanusError,
)
from .errors import (
    VideoRoomLifecycleError as VideoRoomLifecycleError,
)
from .errors import (
    VideoRoomPluginError as VideoRoomPluginError,
)
from .errors import (
    VideoRoomProtocolError as VideoRoomProtocolError,
)
from .models import *  # noqa: F403 - package intentionally re-exports wire models
from .models import parse_videoroom_response as parse_videoroom_response
from .plugin import VideoRoomPlugin as VideoRoomPlugin
from .service import Publisher as Publisher
from .service import Subscriber as Subscriber
from .service import VideoRoomService as VideoRoomService
from .service import VideoRoomServiceMetrics as VideoRoomServiceMetrics

__all__ = sorted(
    name
    for name in globals()
    if not name.startswith("_")
    and (
        name.startswith("VideoRoom")
        or name.startswith("Publisher")
        or name.startswith("Subscriber")
        or name.endswith("Request")
        or name.endswith("Target")
        or name in {"AudioCodec", "VideoCodec", "DummyStream", "RtpForwardStream"}
        or name == "parse_videoroom_response"
    )
)
