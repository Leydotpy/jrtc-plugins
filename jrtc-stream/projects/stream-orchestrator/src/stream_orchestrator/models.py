from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from .errors import InvalidDefinition

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type Metadata = Mapping[str, Any]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _frozen_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


class MediaKind(StrEnum):
    AUDIO = "audio"
    VIDEO = "video"
    DATA = "data"


class DesiredState(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    DELETED = "deleted"


class MountpointState(StrEnum):
    ABSENT = "absent"
    CREATING = "creating"
    DISABLED = "disabled"
    ENABLED = "enabled"
    DESTROYING = "destroying"
    ERROR = "error"


class ProducerState(StrEnum):
    NONE = "none"
    WAITING_FOR_SOURCE = "waiting-for-source"
    PREPARING = "preparing"
    STARTING = "starting"
    RUNNING = "running"
    BACKING_OFF = "backing-off"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class MediaState(StrEnum):
    UNKNOWN = "unknown"
    WARMING = "warming"
    FLOWING = "flowing"
    STALE = "stale"
    ENDED = "ended"


class OperationalState(StrEnum):
    PENDING = "pending"
    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"
    STOPPED = "stopped"


class OperationState(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TrackContract:
    mid: str
    kind: MediaKind
    codec: str
    payload_type: int
    clock_rate: int | None = None
    channels: int | None = None
    fmtp: str | None = None
    required: bool = True

    def __post_init__(self) -> None:
        if not self.mid.strip():
            raise InvalidDefinition("track mid must not be empty")
        if not self.codec.strip():
            raise InvalidDefinition("track codec must not be empty")
        if not 0 <= self.payload_type <= 127:
            raise InvalidDefinition("RTP payload type must be between 0 and 127")
        if self.clock_rate is not None and self.clock_rate <= 0:
            raise InvalidDefinition("clock_rate must be positive")
        if self.channels is not None and self.channels <= 0:
            raise InvalidDefinition("channels must be positive")


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Driver-neutral source description.

    Driver packages own stricter schemas. They convert their validated models to
    this stable core representation before orchestration.
    """

    kind: str
    locator: str | None = None
    settings: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise InvalidDefinition("source kind must not be empty")
        object.__setattr__(self, "settings", _frozen_mapping(self.settings))


@dataclass(frozen=True, slots=True)
class PipelineSpec:
    driver: str
    profile: str | None = None
    settings: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.driver.strip():
            raise InvalidDefinition("pipeline driver must not be empty")
        object.__setattr__(self, "settings", _frozen_mapping(self.settings))


@dataclass(frozen=True, slots=True)
class RestartPolicy:
    mode: str = "on-failure"
    maximum_attempts: int | None = 5
    initial_delay_seconds: float = 1.0
    maximum_delay_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.mode not in {"never", "on-failure", "always"}:
            raise InvalidDefinition("restart mode must be never, on-failure, or always")
        if self.maximum_attempts is not None and self.maximum_attempts < 1:
            raise InvalidDefinition("maximum_attempts must be at least 1")
        if self.initial_delay_seconds <= 0 or self.maximum_delay_seconds <= 0:
            raise InvalidDefinition("restart delays must be positive")
        if self.initial_delay_seconds > self.maximum_delay_seconds:
            raise InvalidDefinition("initial restart delay cannot exceed maximum delay")


@dataclass(frozen=True, slots=True)
class LifecyclePolicy:
    startup_timeout_seconds: float = 30.0
    media_stale_after_seconds: float = 5.0
    drain_timeout_seconds: float = 15.0
    destroy_when_stopped: bool = True
    disable_when_stale: bool = True
    restart: RestartPolicy = field(default_factory=RestartPolicy)

    def __post_init__(self) -> None:
        if self.startup_timeout_seconds <= 0:
            raise InvalidDefinition("startup_timeout_seconds must be positive")
        if self.media_stale_after_seconds <= 0:
            raise InvalidDefinition("media_stale_after_seconds must be positive")
        if self.drain_timeout_seconds < 0:
            raise InvalidDefinition("drain_timeout_seconds must not be negative")


@dataclass(frozen=True, slots=True)
class StreamDefinition:
    name: str
    source: SourceSpec
    pipeline: PipelineSpec
    tracks: tuple[TrackContract, ...]
    id: UUID = field(default_factory=uuid4)
    private: bool = True
    lifecycle: LifecyclePolicy = field(default_factory=LifecyclePolicy)
    tenant_id: str | None = None
    labels: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidDefinition("stream name must not be empty")
        mids = [track.mid for track in self.tracks]
        if len(mids) != len(set(mids)):
            raise InvalidDefinition("track mids must be unique")
        object.__setattr__(self, "labels", MappingProxyType(dict(self.labels)))


@dataclass(frozen=True, slots=True)
class RtpTarget:
    mid: str
    kind: MediaKind
    host: str
    rtp_port: int
    rtcp_port: int | None
    payload_type: int
    codec: str
    fmtp: str | None = None

    def __post_init__(self) -> None:
        for port in (self.rtp_port, self.rtcp_port):
            if port is not None and not 1 <= port <= 65535:
                raise InvalidDefinition("RTP/RTCP ports must be between 1 and 65535")


@dataclass(frozen=True, slots=True)
class MountpointRef:
    backend: str
    instance_id: str
    generation: int
    targets: tuple[RtpTarget, ...] = ()
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _frozen_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class SourceRuntimeRef:
    driver: str
    instance_id: str
    generation: int
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _frozen_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class PreparedSource:
    driver: str
    payload: Any


@dataclass(frozen=True, slots=True)
class SourceContext:
    stream_id: UUID
    generation: int
    targets: tuple[RtpTarget, ...]
    startup_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class GateObservation:
    ready: bool
    state: ProducerState = ProducerState.WAITING_FOR_SOURCE
    reason: str | None = None
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TrackObservation:
    mid: str
    flowing: bool
    packet_age_ms: int | None = None


@dataclass(frozen=True, slots=True)
class MountpointObservation:
    exists: bool
    enabled: bool
    viewer_count: int = 0
    tracks: tuple[TrackObservation, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceObservation:
    state: ProducerState
    healthy: bool
    progress_at: datetime | None = None
    exit_code: int | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class StreamStatus:
    stream_id: UUID
    desired: DesiredState = DesiredState.STOPPED
    generation: int = 0
    mountpoint: MountpointState = MountpointState.ABSENT
    producer: ProducerState = ProducerState.NONE
    media: MediaState = MediaState.UNKNOWN
    operational: OperationalState = OperationalState.STOPPED
    mountpoint_ref: MountpointRef | None = None
    source_ref: SourceRuntimeRef | None = None
    tracks: tuple[TrackObservation, ...] = ()
    restart_count: int = 0
    next_retry_at: datetime | None = None
    reason_code: str | None = None
    reason_message: str | None = None
    last_transition_at: datetime = field(default_factory=utc_now)
    last_heartbeat_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class StreamRecord:
    definition: StreamDefinition
    status: StreamStatus
    revision: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def id(self) -> UUID:
        return self.definition.id


@dataclass(frozen=True, slots=True)
class StreamOperation:
    stream_id: UUID
    action: str
    id: UUID = field(default_factory=uuid4)
    state: OperationState = OperationState.ACCEPTED
    created_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    error: str | None = None
