from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FfmpegProfile:
    name: str
    video_encoder: str | None
    audio_encoder: str | None
    video_options: tuple[str, ...] = ()
    audio_options: tuple[str, ...] = ()
    output_packet_size: int = 1200

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("profile name must not be empty")
        if not 256 <= self.output_packet_size <= 65_507:
            raise ValueError("output_packet_size is outside a safe UDP payload range")


def default_profiles() -> dict[str, FfmpegProfile]:
    return {
        "h264-opus-low-latency": FfmpegProfile(
            name="h264-opus-low-latency",
            video_encoder="libx264",
            audio_encoder="libopus",
            video_options=(
                "-preset",
                "veryfast",
                "-tune",
                "zerolatency",
                "-pix_fmt",
                "yuv420p",
                "-g",
                "60",
                "-keyint_min",
                "60",
                "-sc_threshold",
                "0",
            ),
            audio_options=("-ar", "48000", "-ac", "2"),
        ),
        "vp8-opus-low-latency": FfmpegProfile(
            name="vp8-opus-low-latency",
            video_encoder="libvpx",
            audio_encoder="libopus",
            video_options=(
                "-deadline",
                "realtime",
                "-cpu-used",
                "5",
                "-g",
                "60",
            ),
            audio_options=("-ar", "48000", "-ac", "2"),
        ),
        "copy-video-opus": FfmpegProfile(
            name="copy-video-opus",
            video_encoder="copy",
            audio_encoder="libopus",
            audio_options=("-ar", "48000", "-ac", "2"),
        ),
    }
