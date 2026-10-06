"""Regression tests for backup purging, see issue #208.

These tests exercise `AutoBackup.purge_backups` in isolation by constructing the
manager without a full Home Assistant instance and stubbing its handler/store.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from custom_components.auto_backup.const import EVENT_BACKUPS_PURGED
from custom_components.auto_backup.handlers import HassioAPIError
from custom_components.auto_backup.manager import AutoBackup

EXPIRED = datetime.now(timezone.utc) - timedelta(days=1)


class FakeBus:
    def __init__(self):
        self.events = []

    def async_fire(self, event, data=None):
        self.events.append((event, data))


class FakeHass:
    def __init__(self):
        self.bus = FakeBus()


class FakeStore:
    def __init__(self):
        self.saved = None

    async def async_save(self, data):
        self.saved = dict(data)


class FakeHandler:
    """Handler that fails to delete specific backups with a given error."""

    def __init__(self, failures=None, delay=False):
        self.failures = failures or {}
        self.delay = delay
        self.removed = []

    async def remove_backup(self, slug):
        if self.delay:
            # yield control to the event loop so concurrent purges can interleave
            await asyncio.sleep(0.01)
        error = self.failures.get(slug)
        if error:
            raise HassioAPIError(error)
        self.removed.append(slug)


def make_auto_backup(handler, slugs):
    auto_backup = AutoBackup.__new__(AutoBackup)
    auto_backup._hass = FakeHass()
    auto_backup._handler = handler
    auto_backup._store = FakeStore()
    auto_backup._snapshots = dict.fromkeys(slugs, EXPIRED)
    return auto_backup


def test_successful_purge_removes_tracking():
    auto_backup = make_auto_backup(FakeHandler(), ["aaa", "bbb"])

    asyncio.run(auto_backup.purge_backups())

    assert auto_backup._handler.removed == ["aaa", "bbb"]
    assert auto_backup._snapshots == {}
    assert auto_backup._store.saved == {}
    assert auto_backup._hass.bus.events == [(EVENT_BACKUPS_PURGED, {"backups": ["aaa", "bbb"]})]


def test_transient_failure_keeps_tracking_for_retry():
    """A failed delete must NOT forget the expiry (regression from 770554b)."""
    handler = FakeHandler(failures={"aaa": "Timeout on /backups/aaa request"})
    auto_backup = make_auto_backup(handler, ["aaa"])

    asyncio.run(auto_backup.purge_backups())

    # backup still exists, so its expiry must be retained and retried later
    assert auto_backup._snapshots == {"aaa": EXPIRED}
    assert auto_backup.get_purgeable_snapshots() == ["aaa"]
    # nothing changed, so nothing should have been persisted
    assert auto_backup._store.saved is None
    assert auto_backup._hass.bus.events == []


def test_transient_failure_is_retried_on_next_purge():
    handler = FakeHandler(failures={"aaa": "Timeout on /backups/aaa request"})
    auto_backup = make_auto_backup(handler, ["aaa"])

    asyncio.run(auto_backup.purge_backups())
    del handler.failures["aaa"]  # transient error clears
    asyncio.run(auto_backup.purge_backups())

    assert handler.removed == ["aaa"]
    assert auto_backup._snapshots == {}
    assert auto_backup._store.saved == {}


def test_missing_backup_is_forgotten():
    """A backup deleted externally is dropped from tracking, not retried forever."""
    handler = FakeHandler(failures={"aaa": "Backup does not exist"})
    auto_backup = make_auto_backup(handler, ["aaa"])

    asyncio.run(auto_backup.purge_backups())

    assert auto_backup._snapshots == {}
    assert auto_backup._store.saved == {}


def test_partial_failure_does_not_persist_loss():
    """One failed delete in a batch must not orphan the backup (issue #208).

    Previously the expiry of the failed backup was deleted and, because another
    backup purged successfully, the loss was persisted to storage.
    """
    handler = FakeHandler(failures={"aaa": "Client error on /backups/aaa request"})
    auto_backup = make_auto_backup(handler, ["aaa", "bbb"])

    asyncio.run(auto_backup.purge_backups())

    assert handler.removed == ["bbb"]
    assert auto_backup._snapshots == {"aaa": EXPIRED}
    assert auto_backup._store.saved == {"aaa": EXPIRED}


def test_concurrent_purges_do_not_crash_or_lose_tracking():
    """Overlapping backup jobs can trigger concurrent purges; they must be safe."""
    handler = FakeHandler(
        failures={"aaa": "Timeout on /backups/aaa request"}, delay=True
    )
    auto_backup = make_auto_backup(handler, ["aaa", "bbb"])

    async def run():
        await asyncio.gather(
            auto_backup.purge_backups(),
            auto_backup.purge_backups(),
        )

    asyncio.run(run())

    # 'bbb' purged (once per serialized run at most), 'aaa' still tracked
    assert auto_backup._snapshots == {"aaa": EXPIRED}
    assert auto_backup._store.saved == {"aaa": EXPIRED}
