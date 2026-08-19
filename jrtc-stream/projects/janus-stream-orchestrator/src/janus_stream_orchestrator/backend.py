from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from janus_streaming import (
    AudioTrackSpec,
    DataTrackSpec,
    JanusCommandError,
    RtpMountpointSpec,
    RtspMountpointSpec,
    StreamingAdminClient,
    VideoTrackSpec,
)
from stream_orchestrator import (
    MediaKind,
    MountpointObservation,
    MountpointRef,
    RtpTarget,
    StreamDefinition,
    TrackObservation,
)

JANUS_NO_SUCH_MOUNTPOINT = 455
NATIVE_RTSP_DRIVER = "janus-native-rtsp"


class MountpointSecretProvider(Protocol):
    """Resolve credentials without storing their values in stream metadata."""

    def for_definition(self, definition: StreamDefinition) -> str | None: ...

    def for_ref(self, ref: MountpointRef) -> str | None: ...


class RtspCredentialsProvider(Protocol):
    def __call__(self, definition: StreamDefinition) -> tuple[str | None, str | None]: ...


@dataclass(frozen=True, slots=True)
class JanusBackendSettings:
    rtp_host: str
    permanent: bool = False
    threads: int | None = None
    buffer_keyframes_ms: int | None = None
    buffer_keyframes_bytes: int | None = None

    def __post_init__(self) -> None:
        if not self.rtp_host.strip():
            raise ValueError("rtp_host must not be empty")
        if self.threads is not None and self.threads < 0:
            raise ValueError("threads must not be negative")
        if self.buffer_keyframes_ms is not None and self.buffer_keyframes_ms < 0:
            raise ValueError("buffer_keyframes_ms must not be negative")
        if self.buffer_keyframes_bytes is not None and self.buffer_keyframes_bytes < 0:
            raise ValueError("buffer_keyframes_bytes must not be negative")


class NullSecretProvider:
    def for_definition(self, definition: StreamDefinition) -> None:
        del definition
        return None

    def for_ref(self, ref: MountpointRef) -> None:
        del ref
        return None


class JanusStreamingMountpointBackend:
    """`MountpointBackend` implemented by `jrtc-stream`."""

    name = "janus-streaming"

    def __init__(
        self,
        admin: StreamingAdminClient,
        *,
        settings: JanusBackendSettings,
        secrets: MountpointSecretProvider | None = None,
        rtsp_credentials: RtspCredentialsProvider | None = None,
        pin_for_definition: Callable[[StreamDefinition], str | None] | None = None,
    ) -> None:
        self._admin = admin
        self._settings = settings
        self._secrets = secrets or NullSecretProvider()
        self._rtsp_credentials = rtsp_credentials or (lambda definition: (None, None))
        self._pin_for_definition = pin_for_definition or (lambda definition: None)

    async def create(self, definition: StreamDefinition, *, generation: int) -> MountpointRef:
        if definition.pipeline.driver == NATIVE_RTSP_DRIVER:
            return await self._create_rtsp(definition, generation=generation)
        return await self._create_rtp(definition, generation=generation)

    async def _create_rtp(
        self,
        definition: StreamDefinition,
        *,
        generation: int,
    ) -> MountpointRef:
        media = tuple(self._track_spec(track) for track in definition.tracks)
        if not media:
            raise ValueError("RTP mountpoints require at least one track contract")

        created = await self._admin.create_rtp(
            RtpMountpointSpec(
                name=self._mountpoint_name(definition, generation),
                description=definition.name,
                metadata=self._metadata(definition, generation),
                private=definition.private,
                secret=self._secrets.for_definition(definition),
                pin=self._pin_for_definition(definition),
                enabled=False,
                permanent=self._settings.permanent,
                media=media,
                threads=self._settings.threads,
                buffer_keyframes_ms=self._settings.buffer_keyframes_ms,
                buffer_keyframes_bytes=self._settings.buffer_keyframes_bytes,
            )
        )
        contracts = {track.mid: track for track in definition.tracks}
        targets: list[RtpTarget] = []
        returned_mids: set[str] = set()
        for port in created.ports:
            contract = contracts.get(port.mid)
            if contract is None:
                continue
            if port.mid in returned_mids:
                raise RuntimeError(f"Janus returned duplicate RTP target for mid: {port.mid!r}")
            returned_mids.add(port.mid)
            targets.append(
                RtpTarget(
                    mid=contract.mid,
                    kind=contract.kind,
                    host=self._settings.rtp_host,
                    rtp_port=port.port,
                    # Janus's dynamic create response reports the RTP port.
                    # RTCP may be absent unless configured explicitly.
                    rtcp_port=None,
                    payload_type=contract.payload_type,
                    codec=contract.codec,
                    fmtp=contract.fmtp,
                )
            )
        missing = sorted(set(contracts) - returned_mids)
        if missing:
            raise RuntimeError(f"Janus did not return RTP targets for mids: {missing}")
        return self._ref(definition, generation, created.id, tuple(targets), "rtp")

    async def _create_rtsp(
        self,
        definition: StreamDefinition,
        *,
        generation: int,
    ) -> MountpointRef:
        locator = definition.source.locator
        if not locator:
            raise ValueError("native RTSP sources require source.locator")
        settings = definition.source.settings
        username, password = self._rtsp_credentials(definition)
        created = await self._admin.create_rtsp(
            RtspMountpointSpec(
                url=locator,
                name=self._mountpoint_name(definition, generation),
                description=definition.name,
                metadata=self._metadata(definition, generation),
                private=definition.private,
                secret=self._secrets.for_definition(definition),
                pin=self._pin_for_definition(definition),
                enabled=False,
                permanent=self._settings.permanent,
                username=username,
                password=password,
                reconnect_delay_seconds=self._integer(settings, "reconnect_delay_seconds", 5),
                session_timeout_seconds=self._optional_integer(settings, "session_timeout_seconds"),
                media_timeout_seconds=self._optional_integer(settings, "media_timeout_seconds"),
                connection_timeout_seconds=self._optional_integer(
                    settings, "connection_timeout_seconds"
                ),
                bind_interface=self._optional_string(settings, "bind_interface"),
                notify_changes=self._bool(settings, "notify_changes", True),
                fail_check=self._optional_bool(settings, "fail_check"),
                quirk=self._optional_bool(settings, "quirk"),
            )
        )
        return self._ref(definition, generation, created.id, (), "rtsp")

    async def inspect(self, ref: MountpointRef) -> MountpointObservation:
        try:
            info = await self._admin.info(
                int(ref.instance_id),
                secret=self._secrets.for_ref(ref),
            )
        except JanusCommandError as exc:
            if exc.code == JANUS_NO_SUCH_MOUNTPOINT:
                return MountpointObservation(exists=False, enabled=False)
            raise
        return MountpointObservation(
            exists=True,
            enabled=bool(info.enabled),
            viewer_count=info.viewers,
            tracks=tuple(
                TrackObservation(
                    mid=track.mid,
                    flowing=track.age_ms is not None,
                    packet_age_ms=track.age_ms,
                )
                for track in info.media
            ),
        )

    async def enable(self, ref: MountpointRef) -> None:
        await self._admin.enable(int(ref.instance_id), secret=self._secrets.for_ref(ref))

    async def disable(self, ref: MountpointRef) -> None:
        try:
            await self._admin.disable(int(ref.instance_id), secret=self._secrets.for_ref(ref))
        except JanusCommandError as exc:
            if exc.code != JANUS_NO_SUCH_MOUNTPOINT:
                raise

    async def kick_all(self, ref: MountpointRef) -> None:
        try:
            await self._admin.kick_all(int(ref.instance_id), secret=self._secrets.for_ref(ref))
        except JanusCommandError as exc:
            if exc.code != JANUS_NO_SUCH_MOUNTPOINT:
                raise

    async def destroy(self, ref: MountpointRef) -> None:
        try:
            await self._admin.destroy(
                int(ref.instance_id),
                secret=self._secrets.for_ref(ref),
                permanent=self._settings.permanent,
            )
        except JanusCommandError as exc:
            if exc.code != JANUS_NO_SUCH_MOUNTPOINT:
                raise

    @staticmethod
    def _track_spec(track):
        common = {
            "mid": track.mid,
            "payload_type": track.payload_type,
            "codec": track.codec,
            "fmtp": track.fmtp,
        }
        if track.kind is MediaKind.AUDIO:
            return AudioTrackSpec(**common)
        if track.kind is MediaKind.VIDEO:
            return VideoTrackSpec(**common)
        if track.kind is MediaKind.DATA:
            common.pop("codec")
            common.pop("fmtp")
            common.pop("payload_type")
            return DataTrackSpec(mid=track.mid)
        raise ValueError(f"unsupported media kind: {track.kind}")

    def _ref(
        self,
        definition: StreamDefinition,
        generation: int,
        mountpoint_id: int,
        targets: tuple[RtpTarget, ...],
        mountpoint_type: str,
    ) -> MountpointRef:
        return MountpointRef(
            backend=self.name,
            instance_id=str(mountpoint_id),
            generation=generation,
            targets=targets,
            metadata={
                "stream_id": str(definition.id),
                "generation": generation,
                "mountpoint_type": mountpoint_type,
            },
        )

    @staticmethod
    def _mountpoint_name(definition: StreamDefinition, generation: int) -> str:
        return f"stream-{definition.id}-g{generation}"

    @staticmethod
    def _metadata(definition: StreamDefinition, generation: int) -> str:
        return json.dumps(
            {"stream_id": str(definition.id), "generation": generation},
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _optional_integer(settings, key: str) -> int | None:
        value = settings.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{key} must be an integer")
        return value

    @staticmethod
    def _integer(settings, key: str, default: int) -> int:
        value = settings.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{key} must be an integer")
        return value

    @staticmethod
    def _optional_bool(settings, key: str) -> bool | None:
        value = settings.get(key)
        if value is None:
            return None
        if not isinstance(value, bool):
            raise TypeError(f"{key} must be a boolean")
        return value

    @staticmethod
    def _bool(settings, key: str, default: bool) -> bool:
        value = settings.get(key, default)
        if not isinstance(value, bool):
            raise TypeError(f"{key} must be a boolean")
        return value

    @staticmethod
    def _optional_string(settings, key: str) -> str | None:
        value = settings.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"{key} must be a string")
        return value
