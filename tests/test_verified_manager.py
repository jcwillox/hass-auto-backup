"""Run in a matching Home Assistant Python environment (no live HA required)."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from custom_components.auto_backup.manager import AutoBackup
from custom_components.auto_backup.const import (
    EVENT_BACKUP_SUCCESSFUL,
    EVENT_BACKUP_FAILED,
    EVENT_BACKUP_START,
)


class FlowTests(unittest.IsolatedAsyncioTestCase):
    def manager(self, copy_error=None, create_error=None, enabled=True):
        events = []
        manager = AutoBackup.__new__(AutoBackup)
        manager._state = 0
        manager._backup_timeout = 1200
        manager._auto_purge = True
        manager._snapshots = {}
        manager._manager = None
        manager._hass = SimpleNamespace(
            bus=SimpleNamespace(async_fire=lambda *args: events.append(args))
        )
        manager.validate_backup_config = lambda data: None
        manager._handler = SimpleNamespace(
            create_backup=AsyncMock(
                return_value={"slug": "01234567"}, side_effect=create_error
            )
        )

        async def copy(*args):
            self.assertLess(
                sum(e[0] == EVENT_BACKUP_SUCCESSFUL for e in events),
                sum(e[0] == EVENT_BACKUP_START for e in events),
            )
            if copy_error:
                raise copy_error

        manager._nas = SimpleNamespace(
            enabled=enabled, copy=copy, status={}, failure=lambda *a, **kw: None
        )
        manager.purge_backups = AsyncMock()
        manager.events = events
        return manager

    async def test_success_after_verified_copy_and_then_purge(self):
        manager = self.manager()
        self.assertTrue(await manager.async_create_backup({"name": "unit test"}))
        self.assertTrue(
            any(
                e[0] == EVENT_BACKUP_SUCCESSFUL and e[1]["nas_verified"]
                for e in manager.events
            )
        )
        manager.purge_backups.assert_awaited_once()
        self.assertEqual(manager._state, 0)

    async def test_failed_copy_never_success_or_purge(self):
        manager = self.manager(copy_error=RuntimeError("simulated mismatch"))
        self.assertFalse(await manager.async_create_backup({"name": "unit test"}))
        self.assertFalse(any(e[0] == EVENT_BACKUP_SUCCESSFUL for e in manager.events))
        self.assertTrue(any(e[0] == EVENT_BACKUP_FAILED for e in manager.events))
        manager.purge_backups.assert_not_awaited()
        self.assertEqual(manager._state, 0)

    async def test_failed_local_creation_preserves_previous_copies(self):
        manager = self.manager(create_error=RuntimeError("simulated creation failure"))
        self.assertFalse(await manager.async_create_backup({"name": "unit test"}))
        manager.purge_backups.assert_not_awaited()
        self.assertEqual(manager._state, 0)

    async def test_concurrent_requests_are_serialized(self):
        manager = self.manager()
        active = 0

        async def create(*args, **kwargs):
            nonlocal active
            active += 1
            self.assertEqual(active, 1)
            await asyncio.sleep(0.01)
            active -= 1
            return {"slug": "01234567"}

        manager._handler.create_backup = create
        self.assertEqual(
            await asyncio.gather(
                *(manager.async_create_backup({"name": "unit test"}) for _ in range(2))
            ),
            [True, True],
        )


if __name__ == "__main__":
    unittest.main()
