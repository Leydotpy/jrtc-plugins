"""Public API for the independently installable AudioBridge client."""

from .errors import (
    AudioBridgeError as AudioBridgeError,
    AudioBridgeJanusError as AudioBridgeJanusError,
    AudioBridgePluginError as AudioBridgePluginError,
    AudioBridgeProtocolError as AudioBridgeProtocolError,
)
from .models import *  # noqa: F403 - the package intentionally re-exports wire models
from .models import parse_audiobridge_response as parse_audiobridge_response
from .plugin import AudioBridgePlugin as AudioBridgePlugin

__all__ = sorted(
    name
    for name in globals()
    if name.startswith("AudioBridge") or name == "parse_audiobridge_response"
)
