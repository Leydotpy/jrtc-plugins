from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import django
import pytest
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.management import call_command
from django.db import connections

_fd, _database_path = tempfile.mkstemp(prefix="stream-orchestrator-django-", suffix=".sqlite3")
os.close(_fd)

if not settings.configured:
    settings.configure(
        SECRET_KEY="tests-only",
        INSTALLED_APPS=["stream_orchestrator_django"],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": _database_path,
            }
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
    )
    django.setup()


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    call_command("migrate", verbosity=0, interactive=False)
    try:
        yield
    finally:
        asyncio.run(sync_to_async(connections.close_all, thread_sensitive=True)())
        connections.close_all()
        Path(_database_path).unlink(missing_ok=True)
