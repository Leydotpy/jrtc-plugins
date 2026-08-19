from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GstreamerProfile:
    name: str
    video_encoder: tuple[str, ...] | None
    video_payloader: str | None
    audio_encoder: tuple[str, ...] | None
    audio_payloader: str | None
    video_preprocess: tuple[str, ...] = ("videoconvert",)
    audio_preprocess: tuple[str, ...] = ("audioconvert", "!", "audioresample")

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("profile name must not be empty")


def default_profiles() -> dict[str, GstreamerProfile]:
    return {
        "h264-opus-low-latency": GstreamerProfile(
            name="h264-opus-low-latency",
            video_encoder=(
                "x264enc",
                "tune=zerolatency",
                "speed-preset=veryfast",
                "key-int-max=60",
                "byte-stream=true",
            ),
            video_payloader="rtph264pay",
            audio_encoder=("opusenc",),
            audio_payloader="rtpopuspay",
        ),
        "vp8-opus-low-latency": GstreamerProfile(
            name="vp8-opus-low-latency",
            video_encoder=("vp8enc", "deadline=1", "cpu-used=5", "keyframe-max-dist=60"),
            video_payloader="rtpvp8pay",
            audio_encoder=("opusenc",),
            audio_payloader="rtpopuspay",
        ),
    }
