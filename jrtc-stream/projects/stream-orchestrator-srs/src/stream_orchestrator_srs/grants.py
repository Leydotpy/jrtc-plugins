from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from .models import PublishGrant


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64url(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class HmacPublishGrantIssuer:
    """Creates application-level tokens for an SRS callback or reverse proxy.

    SRS must be configured to validate the token through the host application's
    callback/proxy layer. Generating a token alone does not make the WHIP/RTMP
    endpoint enforce authorization.
    """

    def __init__(
        self,
        *,
        secret: bytes,
        publish_base_url: str,
        issuer: str = "stream-orchestrator",
    ) -> None:
        if len(secret) < 32:
            raise ValueError("HMAC secret must be at least 32 bytes")
        self._secret = secret
        self._base_url = publish_base_url.rstrip("/")
        self._issuer = issuer

    def issue(
        self,
        *,
        stream_id: UUID,
        app: str,
        stream: str,
        protocol: str,
        ttl_seconds: int = 300,
        now: datetime | None = None,
    ) -> PublishGrant:
        if protocol not in {"whip", "rtmp", "srt"}:
            raise ValueError("protocol must be whip, rtmp, or srt")
        if not 1 <= ttl_seconds <= 3600:
            raise ValueError("ttl_seconds must be between 1 and 3600")
        issued_at = now or datetime.now(UTC)
        expires_at = issued_at + timedelta(seconds=ttl_seconds)
        claims = {
            "iss": self._issuer,
            "sub": str(stream_id),
            "app": app,
            "stream": stream,
            "protocol": protocol,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        body = _b64url(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
        signature = _b64url(hmac.new(self._secret, body.encode(), hashlib.sha256).digest())
        token = f"{body}.{signature}"
        endpoint = self._endpoint(protocol=protocol, app=app, stream=stream, token=token)
        return PublishGrant(
            stream_id=stream_id,
            protocol=protocol,
            endpoint=endpoint,
            token=token,
            expires_at=expires_at,
        )

    def verify(self, token: str, *, now: datetime | None = None) -> dict[str, Any]:
        try:
            body, signature = token.split(".", 1)
        except ValueError as exc:
            raise ValueError("invalid publish token") from exc
        expected = _b64url(hmac.new(self._secret, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid publish token signature")
        decoded = json.loads(_unb64url(body))
        if not isinstance(decoded, dict):
            raise ValueError("publish token claims must be a JSON object")
        claims: dict[str, Any] = {str(key): value for key, value in decoded.items()}
        current = int((now or datetime.now(UTC)).timestamp())
        if int(claims["exp"]) < current:
            raise ValueError("publish token has expired")
        if claims.get("iss") != self._issuer:
            raise ValueError("unexpected publish token issuer")
        return claims

    def _endpoint(self, *, protocol: str, app: str, stream: str, token: str) -> str:
        if protocol == "whip":
            query = urlencode({"app": app, "stream": stream, "token": token})
            return f"{self._base_url}/rtc/v1/whip/?{query}"
        if protocol == "rtmp":
            return f"{self._base_url}/{app}/{stream}?{urlencode({'token': token})}"
        stream_id = f"#!::r={app}/{stream},m=publish"
        query = urlencode({"streamid": stream_id, "token": token})
        return f"{self._base_url}?{query}"
