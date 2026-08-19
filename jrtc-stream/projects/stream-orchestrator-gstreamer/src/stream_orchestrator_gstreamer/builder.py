from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from stream_orchestrator import MediaKind, SourceContext, StreamDefinition
from stream_orchestrator_process import ProcessSpec

from .profiles import GstreamerProfile


class GstreamerCommandBuilder:
    def __init__(
        self,
        *,
        profiles: dict[str, GstreamerProfile],
        executable: str = "gst-launch-1.0",
        allowed_schemes: frozenset[str] = frozenset(
            {"file", "http", "https", "rtsp", "rtmp", "rtmps"}
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
            raise ValueError("GStreamer pipeline requires a named profile")
        try:
            profile = self._profiles[profile_name]
        except KeyError as exc:
            raise ValueError(f"unknown GStreamer profile {profile_name!r}") from exc

        locator = definition.source.locator
        if locator is None:
            raise ValueError("GStreamer source requires a locator")
        self._validate_locator(locator)

        argv: list[str] = [
            self._executable,
            "-m",
            "-e",
            "uridecodebin",
            f"uri={locator}",
            "name=source",
        ]
        for target in context.targets:
            if target.kind is MediaKind.DATA:
                raise ValueError("the reference GStreamer driver does not emit Janus data tracks")
            if target.kind is MediaKind.VIDEO:
                if profile.video_encoder is None or profile.video_payloader is None:
                    raise ValueError("profile has no video branch")
                argv.extend(
                    (
                        "source.",
                        "!",
                        "queue",
                        "!",
                        *profile.video_preprocess,
                        "!",
                        *profile.video_encoder,
                        "!",
                        profile.video_payloader,
                        f"pt={target.payload_type}",
                        "config-interval=1",
                        "!",
                        "udpsink",
                        f"host={target.host}",
                        f"port={target.rtp_port}",
                        "sync=false",
                        "async=false",
                    )
                )
            elif target.kind is MediaKind.AUDIO:
                if profile.audio_encoder is None or profile.audio_payloader is None:
                    raise ValueError("profile has no audio branch")
                argv.extend(
                    (
                        "source.",
                        "!",
                        "queue",
                        "!",
                        *profile.audio_preprocess,
                        "!",
                        *profile.audio_encoder,
                        "!",
                        profile.audio_payloader,
                        f"pt={target.payload_type}",
                        "!",
                        "udpsink",
                        f"host={target.host}",
                        f"port={target.rtp_port}",
                        "sync=false",
                        "async=false",
                    )
                )
        if not context.targets:
            raise ValueError("GStreamer pipeline has no RTP targets")
        return ProcessSpec(
            argv=tuple(argv),
            labels={
                "stream_id": str(context.stream_id),
                "generation": str(context.generation),
                "driver": "gstreamer",
            },
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
