from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from .events import StreamEvent
from .models import (
    DesiredState,
    LifecyclePolicy,
    MediaKind,
    MediaState,
    MountpointRef,
    MountpointState,
    OperationalState,
    PipelineSpec,
    ProducerState,
    RestartPolicy,
    RtpTarget,
    SourceRuntimeRef,
    SourceSpec,
    StreamDefinition,
    StreamRecord,
    StreamStatus,
    TrackContract,
    TrackObservation,
)


def _plain_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): item for key, item in value.items()}


def definition_to_dict(value: StreamDefinition) -> dict[str, Any]:
    return {
        "id": str(value.id),
        "name": value.name,
        "source": {
            "kind": value.source.kind,
            "locator": value.source.locator,
            "settings": _plain_mapping(value.source.settings),
        },
        "pipeline": {
            "driver": value.pipeline.driver,
            "profile": value.pipeline.profile,
            "settings": _plain_mapping(value.pipeline.settings),
        },
        "tracks": [
            {
                "mid": item.mid,
                "kind": item.kind.value,
                "codec": item.codec,
                "payload_type": item.payload_type,
                "clock_rate": item.clock_rate,
                "channels": item.channels,
                "fmtp": item.fmtp,
                "required": item.required,
            }
            for item in value.tracks
        ],
        "private": value.private,
        "lifecycle": {
            "startup_timeout_seconds": value.lifecycle.startup_timeout_seconds,
            "media_stale_after_seconds": value.lifecycle.media_stale_after_seconds,
            "drain_timeout_seconds": value.lifecycle.drain_timeout_seconds,
            "destroy_when_stopped": value.lifecycle.destroy_when_stopped,
            "disable_when_stale": value.lifecycle.disable_when_stale,
            "restart": {
                "mode": value.lifecycle.restart.mode,
                "maximum_attempts": value.lifecycle.restart.maximum_attempts,
                "initial_delay_seconds": value.lifecycle.restart.initial_delay_seconds,
                "maximum_delay_seconds": value.lifecycle.restart.maximum_delay_seconds,
            },
        },
        "tenant_id": value.tenant_id,
        "labels": dict(value.labels),
    }


def definition_from_dict(data: Mapping[str, Any]) -> StreamDefinition:
    source = data["source"]
    pipeline = data["pipeline"]
    lifecycle = data["lifecycle"]
    restart = lifecycle["restart"]
    return StreamDefinition(
        id=UUID(str(data["id"])),
        name=str(data["name"]),
        source=SourceSpec(
            kind=str(source["kind"]),
            locator=source.get("locator"),
            settings=source.get("settings", {}),
        ),
        pipeline=PipelineSpec(
            driver=str(pipeline["driver"]),
            profile=pipeline.get("profile"),
            settings=pipeline.get("settings", {}),
        ),
        tracks=tuple(
            TrackContract(
                mid=str(item["mid"]),
                kind=MediaKind(str(item["kind"])),
                codec=str(item["codec"]),
                payload_type=int(item["payload_type"]),
                clock_rate=item.get("clock_rate"),
                channels=item.get("channels"),
                fmtp=item.get("fmtp"),
                required=bool(item.get("required", True)),
            )
            for item in data.get("tracks", [])
        ),
        private=bool(data.get("private", True)),
        lifecycle=LifecyclePolicy(
            startup_timeout_seconds=float(lifecycle["startup_timeout_seconds"]),
            media_stale_after_seconds=float(lifecycle["media_stale_after_seconds"]),
            drain_timeout_seconds=float(lifecycle["drain_timeout_seconds"]),
            destroy_when_stopped=bool(lifecycle["destroy_when_stopped"]),
            disable_when_stale=bool(lifecycle["disable_when_stale"]),
            restart=RestartPolicy(
                mode=str(restart["mode"]),
                maximum_attempts=restart.get("maximum_attempts"),
                initial_delay_seconds=float(restart["initial_delay_seconds"]),
                maximum_delay_seconds=float(restart["maximum_delay_seconds"]),
            ),
        ),
        tenant_id=data.get("tenant_id"),
        labels=data.get("labels", {}),
    )


def _target_to_dict(value: RtpTarget) -> dict[str, Any]:
    return {
        "mid": value.mid,
        "kind": value.kind.value,
        "host": value.host,
        "rtp_port": value.rtp_port,
        "rtcp_port": value.rtcp_port,
        "payload_type": value.payload_type,
        "codec": value.codec,
        "fmtp": value.fmtp,
    }


def _target_from_dict(data: Mapping[str, Any]) -> RtpTarget:
    return RtpTarget(
        mid=str(data["mid"]),
        kind=MediaKind(str(data["kind"])),
        host=str(data["host"]),
        rtp_port=int(data["rtp_port"]),
        rtcp_port=int(data["rtcp_port"]) if data.get("rtcp_port") is not None else None,
        payload_type=int(data["payload_type"]),
        codec=str(data["codec"]),
        fmtp=data.get("fmtp"),
    )


def status_to_dict(value: StreamStatus) -> dict[str, Any]:
    mountpoint_ref = None
    if value.mountpoint_ref is not None:
        mountpoint_ref = {
            "backend": value.mountpoint_ref.backend,
            "instance_id": value.mountpoint_ref.instance_id,
            "generation": value.mountpoint_ref.generation,
            "targets": [_target_to_dict(item) for item in value.mountpoint_ref.targets],
            "metadata": dict(value.mountpoint_ref.metadata),
        }
    source_ref = None
    if value.source_ref is not None:
        source_ref = {
            "driver": value.source_ref.driver,
            "instance_id": value.source_ref.instance_id,
            "generation": value.source_ref.generation,
            "metadata": dict(value.source_ref.metadata),
        }
    return {
        "stream_id": str(value.stream_id),
        "desired": value.desired.value,
        "generation": value.generation,
        "mountpoint": value.mountpoint.value,
        "producer": value.producer.value,
        "media": value.media.value,
        "operational": value.operational.value,
        "mountpoint_ref": mountpoint_ref,
        "source_ref": source_ref,
        "tracks": [
            {
                "mid": item.mid,
                "flowing": item.flowing,
                "packet_age_ms": item.packet_age_ms,
            }
            for item in value.tracks
        ],
        "restart_count": value.restart_count,
        "next_retry_at": value.next_retry_at.isoformat() if value.next_retry_at else None,
        "reason_code": value.reason_code,
        "reason_message": value.reason_message,
        "last_transition_at": value.last_transition_at.isoformat(),
        "last_heartbeat_at": (
            value.last_heartbeat_at.isoformat() if value.last_heartbeat_at else None
        ),
    }


def status_from_dict(data: Mapping[str, Any]) -> StreamStatus:
    mountpoint_data = data.get("mountpoint_ref")
    mountpoint_ref = None
    if mountpoint_data:
        mountpoint_ref = MountpointRef(
            backend=str(mountpoint_data["backend"]),
            instance_id=str(mountpoint_data["instance_id"]),
            generation=int(mountpoint_data["generation"]),
            targets=tuple(_target_from_dict(item) for item in mountpoint_data.get("targets", [])),
            metadata=mountpoint_data.get("metadata", {}),
        )
    source_data = data.get("source_ref")
    source_ref = None
    if source_data:
        source_ref = SourceRuntimeRef(
            driver=str(source_data["driver"]),
            instance_id=str(source_data["instance_id"]),
            generation=int(source_data["generation"]),
            metadata=source_data.get("metadata", {}),
        )
    return StreamStatus(
        stream_id=UUID(str(data["stream_id"])),
        desired=DesiredState(str(data["desired"])),
        generation=int(data["generation"]),
        mountpoint=MountpointState(str(data["mountpoint"])),
        producer=ProducerState(str(data["producer"])),
        media=MediaState(str(data["media"])),
        operational=OperationalState(str(data["operational"])),
        mountpoint_ref=mountpoint_ref,
        source_ref=source_ref,
        tracks=tuple(
            TrackObservation(
                mid=str(item["mid"]),
                flowing=bool(item["flowing"]),
                packet_age_ms=item.get("packet_age_ms"),
            )
            for item in data.get("tracks", [])
        ),
        restart_count=int(data.get("restart_count", 0)),
        next_retry_at=(
            datetime.fromisoformat(str(data["next_retry_at"]))
            if data.get("next_retry_at")
            else None
        ),
        reason_code=data.get("reason_code"),
        reason_message=data.get("reason_message"),
        last_transition_at=datetime.fromisoformat(str(data["last_transition_at"])),
        last_heartbeat_at=(
            datetime.fromisoformat(str(data["last_heartbeat_at"]))
            if data.get("last_heartbeat_at")
            else None
        ),
    )


def record_to_dict(value: StreamRecord) -> dict[str, Any]:
    return {
        "definition": definition_to_dict(value.definition),
        "status": status_to_dict(value.status),
        "revision": value.revision,
        "created_at": value.created_at.isoformat(),
        "updated_at": value.updated_at.isoformat(),
    }


def record_from_dict(data: Mapping[str, Any]) -> StreamRecord:
    return StreamRecord(
        definition=definition_from_dict(data["definition"]),
        status=status_from_dict(data["status"]),
        revision=int(data["revision"]),
        created_at=datetime.fromisoformat(str(data["created_at"])),
        updated_at=datetime.fromisoformat(str(data["updated_at"])),
    )


def event_to_dict(value: StreamEvent) -> dict[str, Any]:
    return {
        "id": str(value.id),
        "kind": value.kind,
        "stream_id": str(value.stream_id),
        "generation": value.generation,
        "data": dict(value.data),
        "occurred_at": value.occurred_at.isoformat(),
    }
