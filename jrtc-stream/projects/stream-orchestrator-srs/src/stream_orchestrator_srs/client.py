from __future__ import annotations

from typing import Any

import httpx

from .models import SrsStreamObservation


class SrsApiError(RuntimeError):
    pass


class SrsClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        auth = (username, password or "") if username else None
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            auth=auth,
            headers={"Accept": "application/json"},
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def list_streams(self, *, start: int = 0, count: int = 100) -> tuple[dict[str, Any], ...]:
        response = await self._client.get(
            "/api/v1/streams",
            params={"start": start, "count": count},
        )
        payload = self._decode(response)
        streams = payload.get("streams", [])
        if not isinstance(streams, list):
            raise SrsApiError("SRS streams response is malformed")
        return tuple(item for item in streams if isinstance(item, dict))

    async def inspect_stream(
        self,
        *,
        app: str,
        stream: str,
        vhost: str = "__defaultVhost__",
    ) -> SrsStreamObservation:
        for item in await self.list_streams():
            item_name = str(item.get("name") or item.get("stream") or "")
            item_app = str(item.get("app") or "")
            item_vhost = str(item.get("vhost") or "__defaultVhost__")
            publish_value = item.get("publish")
            publish: dict[str, Any] = publish_value if isinstance(publish_value, dict) else {}
            if item_name == stream and item_app == app and item_vhost == vhost:
                video_value = item.get("video")
                audio_value = item.get("audio")
                video: dict[str, Any] = video_value if isinstance(video_value, dict) else {}
                audio: dict[str, Any] = audio_value if isinstance(audio_value, dict) else {}
                return SrsStreamObservation(
                    published=bool(publish.get("active", True)),
                    stream_id=(str(item["id"]) if item.get("id") is not None else None),
                    client_id=(str(publish["cid"]) if publish.get("cid") is not None else None),
                    vhost=item_vhost,
                    app=item_app,
                    stream=item_name,
                    video_codec=(str(video["codec"]) if video.get("codec") else None),
                    audio_codec=(str(audio["codec"]) if audio.get("codec") else None),
                    raw=item,
                )
        return SrsStreamObservation(
            published=False,
            vhost=vhost,
            app=app,
            stream=stream,
        )

    async def disconnect_client(self, client_id: str) -> None:
        response = await self._client.delete(f"/api/v1/clients/{client_id}")
        self._decode(response)

    @staticmethod
    def _decode(response: httpx.Response) -> dict[str, Any]:
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SrsApiError(f"SRS request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise SrsApiError("SRS response is not a JSON object")
        code = payload.get("code", 0)
        if code not in (0, "0", None):
            raise SrsApiError(f"SRS returned code {code}: {payload.get('message') or payload}")
        return payload
