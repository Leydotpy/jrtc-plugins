from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SrsStreamObservation:
    published: bool
    stream_id: str | None = None
    client_id: str | None = None
    vhost: str | None = None
    app: str | None = None
    stream: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SrsCallbackEvent:
    action: str
    vhost: str
    app: str
    stream: str
    client_id: str | None = None
    request_id: str | None = None
    param: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SrsCallbackEvent:
        action = str(data.get("action", ""))
        if action not in {"on_publish", "on_unpublish", "on_play", "on_stop"}:
            raise ValueError(f"unsupported SRS callback action {action!r}")
        for required in ("vhost", "app", "stream"):
            if not data.get(required):
                raise ValueError(f"SRS callback is missing {required!r}")
        return cls(
            action=action,
            vhost=str(data["vhost"]),
            app=str(data["app"]),
            stream=str(data["stream"]),
            client_id=(str(data["client_id"]) if data.get("client_id") else None),
            request_id=(str(data["request_id"]) if data.get("request_id") else None),
            param=(str(data["param"]) if data.get("param") else None),
            raw=dict(data),
        )


@dataclass(frozen=True, slots=True)
class PublishGrant:
    stream_id: UUID
    protocol: str
    endpoint: str
    token: str
    expires_at: datetime
