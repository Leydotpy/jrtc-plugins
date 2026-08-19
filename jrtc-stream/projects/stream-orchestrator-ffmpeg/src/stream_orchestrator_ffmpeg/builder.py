from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlencode, urlparse

from stream_orchestrator import MediaKind, SourceContext, StreamDefinition
from stream_orchestrator_process import ProcessSpec

from .profiles import FfmpegProfile


class FfmpegProgressParser:
    def __call__(self, line: str) -> Mapping[str, str] | None:
        if "=" not in line:
            return None
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            return None
        return {key: value.strip()}


class FfmpegCommandBuilder:
    def __init__(
        self,
        *,
        profiles: dict[str, FfmpegProfile],
        executable: str = "ffmpeg",
        allowed_schemes: frozenset[str] = frozenset(
            {"file", "http", "https", "rtsp", "rtmp", "rtmps", "srt", "udp"}
        ),
        allowed_file_roots: tuple[Path, ...] = (),
    ) -> None:
        self._profiles = dict(profiles)
        self._executable = executable
        self._allowed_schemes = allowed_schemes
        self._allowed_file_roots = tuple(path.resolve() for path in allowed_file_roots)

    def build(self, context: SourceContext, definition: StreamDefinition) -> ProcessSpec:
        profile_name = definition.pipeline.profile
        if profile_name is None:
            raise ValueError("FFmpeg pipeline requires a named profile")
        try:
            profile = self._profiles[profile_name]
        except KeyError as exc:
            raise ValueError(f"unknown FFmpeg profile {profile_name!r}") from exc

        locator = definition.source.locator
        if locator is None:
            raise ValueError("FFmpeg source requires a locator")
        self._validate_locator(locator)

        argv: list[str] = [
            self._executable,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-stats_period",
            "1",
            "-progress",
            "pipe:1",
        ]
        if bool(definition.pipeline.settings.get("realtime_input", False)):
            argv.append("-re")
        if definition.source.kind == "rtsp":
            transport = str(definition.source.settings.get("transport", "tcp"))
            if transport not in {"tcp", "udp", "udp_multicast", "http", "https"}:
                raise ValueError(f"unsupported RTSP transport {transport!r}")
            argv.extend(("-rtsp_transport", transport))
        argv.extend(("-i", locator))

        video_targets = [item for item in context.targets if item.kind is MediaKind.VIDEO]
        audio_targets = [item for item in context.targets if item.kind is MediaKind.AUDIO]
        data_targets = [item for item in context.targets if item.kind is MediaKind.DATA]
        if data_targets:
            raise ValueError("the reference FFmpeg driver does not emit Janus data tracks")

        for index, target in enumerate(video_targets):
            if profile.video_encoder is None:
                raise ValueError("profile has no video encoder")
            argv.extend(
                (
                    "-map",
                    f"0:v:{index}",
                    "-an",
                    "-c:v",
                    profile.video_encoder,
                    *profile.video_options,
                    "-payload_type",
                    str(target.payload_type),
                    "-f",
                    "rtp",
                    self._rtp_url(target.host, target.rtp_port, profile.output_packet_size),
                )
            )

        for index, target in enumerate(audio_targets):
            if profile.audio_encoder is None:
                raise ValueError("profile has no audio encoder")
            argv.extend(
                (
                    "-map",
                    f"0:a:{index}",
                    "-vn",
                    "-c:a",
                    profile.audio_encoder,
                    *profile.audio_options,
                    "-payload_type",
                    str(target.payload_type),
                    "-f",
                    "rtp",
                    self._rtp_url(target.host, target.rtp_port, profile.output_packet_size),
                )
            )

        if not video_targets and not audio_targets:
            raise ValueError("FFmpeg pipeline has no audio or video RTP targets")

        environment_value = definition.pipeline.settings.get("environment", {})
        environment = (
            {str(key): str(value) for key, value in environment_value.items()}
            if isinstance(environment_value, dict)
            else {}
        )

        return ProcessSpec(
            argv=tuple(argv),
            environment=environment,
            labels={
                "stream_id": str(context.stream_id),
                "generation": str(context.generation),
                "driver": "ffmpeg",
            },
            progress_parser=FfmpegProgressParser(),
        )

    def _validate_locator(self, locator: str) -> None:
        parsed = urlparse(locator)
        scheme = parsed.scheme.lower()
        if scheme not in self._allowed_schemes:
            raise ValueError(f"source scheme {scheme!r} is not allowed")
        if scheme == "file":
            path = Path(parsed.path).resolve()
            if self._allowed_file_roots and not any(
                path == root or root in path.parents for root in self._allowed_file_roots
            ):
                raise PermissionError(f"file source {path} is outside configured media roots")

    @staticmethod
    def _rtp_url(host: str, port: int, packet_size: int) -> str:
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"rtp://{host}:{port}?{urlencode({'pkt_size': packet_size})}"
