from __future__ import annotations

import uuid

from django.db import models


class OrchestratedStream(models.Model):
    """Serialized core record plus query-friendly state projections."""

    id = models.UUIDField(primary_key=True, editable=False)
    definition = models.JSONField()
    status = models.JSONField()
    revision = models.PositiveBigIntegerField(default=0)
    desired_state = models.CharField(max_length=32, db_index=True)
    operational_state = models.CharField(max_length=32, db_index=True)
    tenant_id = models.CharField(max_length=200, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("id",)
        indexes = [
            models.Index(
                fields=("desired_state", "operational_state"),
                name="so_desired_oper_idx",
            ),
            models.Index(
                fields=("tenant_id", "desired_state"),
                name="so_tenant_desired_idx",
            ),
        ]


class OrchestratorEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stream_id = models.UUIDField(db_index=True)
    kind = models.CharField(max_length=120, db_index=True)
    generation = models.PositiveBigIntegerField(default=0)
    data = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("occurred_at", "id")
        indexes = [
            models.Index(
                fields=("stream_id", "occurred_at"),
                name="so_event_stream_time_idx",
            )
        ]


class OrchestratorOutbox(models.Model):
    """Optional transactional-outbox row for external event publication."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.CharField(max_length=200)
    stream_id = models.UUIDField(db_index=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [
            models.Index(
                fields=("published_at", "created_at"),
                name="so_outbox_pending_idx",
            )
        ]
