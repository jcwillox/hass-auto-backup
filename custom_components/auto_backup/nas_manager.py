"""HA lifecycle, receipts and notifications for verified NAS backups."""

import asyncio
from datetime import datetime, timedelta
import logging
import re
import uuid

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import nas_backend

EVENT_NAS_UPDATED = "auto_backup.nas_updated"
EVENT_NAS_FAILED = "auto_backup.nas_failed"
_LOGGER = logging.getLogger(__name__)


def config_from_options(options):
    return {
        "enabled": options.get("nas_enabled", False),
        "server": options.get("nas_server", ""),
        "share": options.get("nas_share", ""),
        "folder": options.get("nas_folder", ""),
        "username": options.get("nas_username", ""),
        "password": options.get("nas_password", ""),
        "workgroup": options.get("nas_workgroup", "WORKGROUP"),
        "daily": options.get("nas_daily", 7),
        "weekly": options.get("nas_weekly", 4),
        "monthly": options.get("nas_monthly", 2),
        "keep_local": options.get("nas_keep_local", 1),
        "manage_legacy": options.get("nas_manage_legacy", False),
    }


class NasBackupManager:
    def __init__(self, hass, options, handler):
        self.hass, self.handler = hass, handler
        self.config = config_from_options(options)
        self.store = Store(hass, 1, "auto_backup.nas_verification")
        self.namespace = None
        self.receipts = {}
        self.status = {"status": "disabled" if not self.enabled else "waiting"}
        self.lock = asyncio.Lock()
        self.cancels = []

    @property
    def enabled(self):
        return self.config["enabled"]

    async def load(self):
        saved = await self.store.async_load() or {}
        self.namespace = saved.get("namespace") or uuid.uuid4().hex[:12]
        self.receipts = saved.get("receipts", {})
        self.status.update(saved.get("status", {}))
        if not self.enabled:
            self.status["status"] = "disabled"
        await self.save()
        self.start()

    async def save(self):
        await self.store.async_save(
            {
                "namespace": self.namespace,
                "receipts": self.receipts,
                "status": self.status,
            }
        )

    def publish(self, **values):
        self.status.update(values)
        if self.status.get("integrity_error") and self.status.get("status") in [
            "ok",
            "verified",
        ]:
            self.status["status"] = "error"
        self.hass.bus.async_fire(EVENT_NAS_UPDATED, dict(self.status))

    def failure(self, operation, error, notify=True):
        # Do not emit configuration, passwords or SMB wire dumps in events/logs.
        if operation in ["verify", "retention"] and isinstance(
            error, nas_backend.ChecksumMismatch
        ):
            self.status["integrity_error"] = True
        self.publish(
            status="error",
            last_error=f"{operation}: {type(error).__name__}",
            last_error_stage=operation,
        )
        if notify:
            self.hass.bus.async_fire(
                EVENT_NAS_FAILED,
                {"operation": operation, "error_type": type(error).__name__},
            )

    def stop(self):
        for cancel in self.cancels:
            cancel()
        self.cancels.clear()

    def start(self):
        self.stop()
        if not self.enabled:
            return
        self.cancels.append(async_call_later(self.hass, 30, self._scheduled_check))
        self.cancels.append(
            async_track_time_interval(
                self.hass, self._scheduled_check, timedelta(hours=1)
            )
        )

    async def update_options(self, options):
        self.config = config_from_options(options)
        if self.enabled:
            nas_backend.validate_config(self.config)
        self.publish(status="waiting" if self.enabled else "disabled")
        self.start()

    async def _scheduled_check(self, _):
        if self.lock.locked():
            return
        try:
            await self.check(notify=False)
        except HomeAssistantError:
            pass

    async def check(self, notify=True):
        if not self.enabled:
            return {"status": "disabled"}
        if self.lock.locked():
            return dict(self.status)
        async with self.lock:
            try:
                result = await self.hass.async_add_executor_job(
                    nas_backend.scan, dict(self.config), self.namespace, dt_util.now()
                )
                if self.status.get("last_error_stage") == "check":
                    self.status.update(last_error=None, last_error_stage=None)
                self.publish(
                    **{k: v for k, v in result.items() if k != "plan"},
                    checked_at=dt_util.now().isoformat(),
                )
                await self.save()
                return result
            except Exception as error:
                self.failure("check", error, notify)
                await self.save()
                raise HomeAssistantError(
                    "NAS check failed (" + type(error).__name__ + ")"
                ) from None

    async def copy(self, slug, when):
        if not hasattr(self.handler, "open_backup_stream"):
            raise HomeAssistantError(
                "Verified NAS backups require Home Assistant OS/Supervisor"
            )
        async with self.lock:
            self.publish(status="copying", last_error=None, last_error_stage=None)
            try:
                receipt = await self.hass.async_add_executor_job(
                    nas_backend.transfer,
                    dict(self.config),
                    self.namespace,
                    slug,
                    when,
                    lambda: self.handler.open_backup_stream(slug),
                )
                receipt["created_at"] = when.isoformat()
                self.receipts[receipt["name"]] = receipt
                self.publish(
                    status="verified",
                    last_backup=when.isoformat(),
                    last_verified=receipt["verified_at"],
                    last_sha256=receipt["sha256"],
                    last_backup_size=receipt["bytes"],
                    checksum="matched",
                )
                await self.save()
                return receipt
            except Exception as error:
                self.failure("copy", error, notify=False)
                await self.save()
                raise HomeAssistantError(
                    "NAS copy or SHA-256 verification failed ("
                    + type(error).__name__
                    + ")"
                ) from None

    async def purge(self):
        async with self.lock:
            try:
                if self.status.get("integrity_error"):
                    raise nas_backend.NasError(
                        "Integrity error is unresolved: retention suspended"
                    )
                result = await self.hass.async_add_executor_job(
                    nas_backend.purge,
                    dict(self.config),
                    self.namespace,
                    dict(self.receipts),
                    dt_util.now(),
                )
                for name in result["removed"]:
                    if name in self.receipts:
                        self.receipts[name]["nas_removed"] = True
                # Only delete local archives that this integration verified on NAS.
                candidates = sorted(
                    (
                        r
                        for r in self.receipts.values()
                        if r.get("slug") and not r.get("local_removed")
                    ),
                    key=lambda r: r.get("created_at", ""),
                    reverse=True,
                )
                local = await self.handler.get_backups()
                slugs = {r["slug"] for r in local}
                for receipt in candidates[self.config["keep_local"] :]:
                    if receipt["slug"] in slugs:
                        await self.handler.remove_backup(receipt["slug"])
                    receipt["local_removed"] = True
                self.receipts = {
                    n: r
                    for n, r in self.receipts.items()
                    if not (
                        r.get("nas_removed")
                        and (r.get("local_removed") or not r.get("slug"))
                    )
                }
                self.publish(last_purged=len(result["removed"]))
                await self.save()
            except Exception as error:
                self.failure("retention", error)
                await self.save()
                raise HomeAssistantError(
                    "NAS retention was not completed (" + type(error).__name__ + ")"
                ) from None
        await self.check()
        return result

    async def verify(self, adopt_legacy=False):
        if not self.enabled:
            raise HomeAssistantError("NAS backups are disabled")
        async with self.lock:
            self.publish(status="verifying", last_error=None)
            try:
                result = await self.hass.async_add_executor_job(
                    nas_backend.verify,
                    dict(self.config),
                    self.namespace,
                    dict(self.receipts),
                    dt_util.now(),
                    adopt_legacy,
                )
                if adopt_legacy:
                    # Adopt a matching surviving local archive only after hashing
                    # it independently. Never prune unrelated manual backups.
                    for local in await self.handler.get_backups():
                        name = (
                            re.sub(r"[^A-Za-z0-9_]", "_", local.get("name", ""))
                            + ".tar"
                        )
                        receipt = result["receipts"].get(name)
                        if receipt and nas_backend.LEGACY.fullmatch(name):
                            digest, size = await self.hass.async_add_executor_job(
                                nas_backend.source_digest,
                                lambda slug=local[
                                    "slug"
                                ]: self.handler.open_backup_stream(slug),
                            )
                            if digest != receipt["sha256"] or size != receipt["bytes"]:
                                raise nas_backend.ChecksumMismatch(
                                    "Existing local and NAS backups differ"
                                )
                            receipt.update(
                                slug=local["slug"],
                                local_removed=False,
                                verification="source_and_nas_sha256",
                            )
                self.receipts.update(result["receipts"])
                self.status.update(
                    integrity_error=False, last_error=None, last_error_stage=None
                )
                self.publish(
                    status="ok" if not result["missing"] else "missing_checksums",
                    last_archive_check=result["verified_at"],
                    checked_archives=len(result["checked"]),
                    missing_checksums=len(result["missing"]),
                    legacy_baselines=len(result["adopted"]),
                )
                await self.save()
                return {k: v for k, v in result.items() if k != "receipts"}
            except Exception as error:
                self.failure("verify", error)
                await self.save()
                raise HomeAssistantError(
                    "NAS integrity verification failed (" + type(error).__name__ + ")"
                ) from None
