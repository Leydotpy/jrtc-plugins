from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from django.db import IntegrityError
from stream_orchestrator import (
    ConcurrencyConflict,
    StreamAlreadyExists,
    StreamNotFound,
    StreamRecord,
)
from stream_orchestrator.serde import record_from_dict, record_to_dict

from .models import OrchestratedStream


class DjangoStreamRepository:
    """Optimistic-concurrency repository implemented with Django's async ORM."""

    async def create(self, record: StreamRecord) -> StreamRecord:
        payload = record_to_dict(record)
        try:
            await OrchestratedStream.objects.acreate(
                id=record.id,
                definition=payload["definition"],
                status=payload["status"],
                revision=record.revision,
                desired_state=record.status.desired.value,
                operational_state=record.status.operational.value,
                tenant_id=record.definition.tenant_id,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
        except IntegrityError as exc:
            raise StreamAlreadyExists(record.id) from exc
        return record

    async def get(self, stream_id: UUID) -> StreamRecord:
        try:
            row = await OrchestratedStream.objects.aget(pk=stream_id)
        except OrchestratedStream.DoesNotExist as exc:
            raise StreamNotFound(stream_id) from exc
        return self._to_record(row)

    async def list(self) -> tuple[StreamRecord, ...]:
        values: list[StreamRecord] = []
        async for row in OrchestratedStream.objects.all().aiterator(chunk_size=200):
            values.append(self._to_record(row))
        return tuple(values)

    async def save(self, record: StreamRecord, *, expected_revision: int) -> StreamRecord:
        updated = replace(
            record,
            revision=expected_revision + 1,
            updated_at=datetime.now(UTC),
        )
        payload = record_to_dict(updated)
        changed = await OrchestratedStream.objects.filter(
            pk=record.id,
            revision=expected_revision,
        ).aupdate(
            definition=payload["definition"],
            status=payload["status"],
            revision=updated.revision,
            desired_state=updated.status.desired.value,
            operational_state=updated.status.operational.value,
            tenant_id=updated.definition.tenant_id,
            updated_at=updated.updated_at,
        )
        if changed == 1:
            return updated

        actual = (
            await OrchestratedStream.objects.filter(pk=record.id)
            .values_list("revision", flat=True)
            .afirst()
        )
        if actual is None:
            raise StreamNotFound(record.id)
        raise ConcurrencyConflict(record.id, expected_revision, int(actual))

    async def delete(self, stream_id: UUID, *, expected_revision: int) -> None:
        deleted, _ = await OrchestratedStream.objects.filter(
            pk=stream_id,
            revision=expected_revision,
        ).adelete()
        if deleted == 1:
            return
        actual = (
            await OrchestratedStream.objects.filter(pk=stream_id)
            .values_list("revision", flat=True)
            .afirst()
        )
        if actual is None:
            raise StreamNotFound(stream_id)
        raise ConcurrencyConflict(stream_id, expected_revision, int(actual))

    @staticmethod
    def _to_record(row: OrchestratedStream) -> StreamRecord:
        return record_from_dict(
            {
                "definition": row.definition,
                "status": row.status,
                "revision": row.revision,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }
        )
