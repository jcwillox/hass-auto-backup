"""Tests for SupervisorHandler error handling of the Supervisor API.

Supervisor raises APINotFound("Backup does not exist") with HTTP 404 for unknown
backup slugs (see supervisor/api/backups.py `_extract_slug`), so that message
must survive to `AutoBackup._purge_snapshot` for expired-tracking cleanup.
"""

import asyncio

import pytest

from custom_components.auto_backup.handlers import HassioAPIError, SupervisorHandler


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def json(self):
        return self._body


class FakeSession:
    def __init__(self, status, body):
        self._response = FakeResponse(status, body)

    async def request(self, *args, **kwargs):
        return self._response


def make_handler(status, body):
    return SupervisorHandler("supervisor", FakeSession(status, body))


def test_remove_backup_success():
    handler = make_handler(200, {"result": "ok", "data": {}})
    assert asyncio.run(handler.remove_backup("slug")) == {}


def test_remove_backup_missing_backup_surfaces_api_message():
    handler = make_handler(
        404, {"result": "error", "message": "Backup does not exist"}
    )
    with pytest.raises(HassioAPIError, match="^Backup does not exist$"):
        asyncio.run(handler.remove_backup("slug"))


def test_remove_backup_surfaces_error_message_from_400():
    handler = make_handler(400, {"result": "error", "message": "boom"})
    with pytest.raises(HassioAPIError, match="boom"):
        asyncio.run(handler.remove_backup("slug"))
