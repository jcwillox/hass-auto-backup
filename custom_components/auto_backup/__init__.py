"""Component to create and remove Hass.io snapshots."""

import logging
from datetime import datetime, timedelta, timezone
import voluptuous as vol

from homeassistant.components.hassio.handler import HassioAPIError, HassIO
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceCallType
from homeassistant.components.hassio import (
    DOMAIN as HASSIO_DOMAIN,
    SERVICE_SNAPSHOT_FULL,
    SERVICE_SNAPSHOT_PARTIAL,
    SCHEMA_SNAPSHOT_FULL,
    SCHEMA_SNAPSHOT_PARTIAL,
)
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import Store
import homeassistant.helpers.config_validation as cv
from homeassistant.const import ATTR_NAME

_LOGGER = logging.getLogger(__name__)

DOMAIN = "auto_backup"
STORAGE_KEY = "snapshots_expiry"
STORAGE_VERSION = 1

ATTR_KEEP_DAYS = "keep_days"

CONF_AUTO_PURGE = "auto_purge"

SERVICE_PURGE = "purge"

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: {vol.Optional(CONF_AUTO_PURGE, default=True): cv.boolean}},
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_SNAPSHOT_FULL = SCHEMA_SNAPSHOT_FULL.extend(
    {vol.Optional(ATTR_KEEP_DAYS): vol.Coerce(float)}
)

SCHEMA_SNAPSHOT_PARTIAL = SCHEMA_SNAPSHOT_PARTIAL.extend(
    {vol.Optional(ATTR_KEEP_DAYS): vol.Coerce(float)}
)

COMMAND_SNAPSHOT_FULL = "/snapshots/new/full"
COMMAND_SNAPSHOT_PARTIAL = "/snapshots/new/partial"
COMMAND_SNAPSHOT_REMOVE = "/snapshots/{slug}/remove"


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Setup"""
    config = config[DOMAIN]
    hassio = hass.data.get(HASSIO_DOMAIN)
    if hassio is None:
        _LOGGER.error("Hass.io not found, please check you have hassio installed!")
        return False

    if not hassio.is_connected():
        _LOGGER.error("Not connected with Hass.io / system to busy!")
        return False

    # initialise AutoBackup class.
    auto_backup = AutoBackup(hass, hassio, config[CONF_AUTO_PURGE])
    await auto_backup.load_snapshots_expiry()

    # register services.
    async def snapshot_service_handler(call: ServiceCallType):
        """Handle Snapshot Creation Service Calls."""
        await auto_backup.new_snapshot(
            call.data.copy(), call.service == SERVICE_SNAPSHOT_FULL
        )

    async def purge_service_handler(call: ServiceCallType):
        """Handle Snapshot Purge Service Calls."""
        await auto_backup.purge_snapshots()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SNAPSHOT_FULL,
        snapshot_service_handler,
        schema=SCHEMA_SNAPSHOT_FULL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SNAPSHOT_PARTIAL,
        snapshot_service_handler,
        schema=SCHEMA_SNAPSHOT_PARTIAL,
    )

    hass.services.async_register(DOMAIN, SERVICE_PURGE, purge_service_handler)

    return True


class AutoBackup:
    def __init__(self, hass: HomeAssistantType, hassio: HassIO, auto_purge: bool):
        self._hass = hass
        self._hassio = hassio
        self._snapshots_store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{STORAGE_KEY}", encoder=JSONEncoder
        )
        self._snapshots_expiry = {}
        self._auto_purge = auto_purge

    async def load_snapshots_expiry(self):
        data = await self._snapshots_store.async_load()

        if data is not None:
            for slug, expiry in data.items():
                self._snapshots_expiry[slug] = datetime.fromisoformat(expiry)

    async def new_snapshot(self, data, full=False):
        _LOGGER.debug("Creating snapshot %s", data[ATTR_NAME])

        command = COMMAND_SNAPSHOT_FULL if full else COMMAND_SNAPSHOT_PARTIAL
        keep_days = data.pop(ATTR_KEEP_DAYS, None)

        _LOGGER.debug(
            "New snapshot; command: %s, keep_days: %s, data: %s",
            command,
            keep_days,
            data,
        )

        try:
            result = await self._hassio.send_command(command, payload=data, timeout=300)

            _LOGGER.debug("Snapshot create result: %s" % result)

            slug = result.get("data", {}).get("slug")
            if slug is None:
                raise HassioAPIError("No slug was returned.")

            # snapshot creation was successful
            _LOGGER.info(
                "Snapshot created successfully; '%s' (%s)", data[ATTR_NAME], slug
            )

            if keep_days is not None:
                # set snapshot expiry
                self._snapshots_expiry[slug] = datetime.now(timezone.utc) + timedelta(
                    days=float(keep_days)
                )
                # write snapshot expiry to storage
                await self._snapshots_store.async_save(self._snapshots_expiry)

            # purging old snapshots
            if self._auto_purge:
                await self.purge_snapshots()

        except HassioAPIError as err:
            _LOGGER.error("Error on Hass.io API: %s", err)

    async def purge_snapshots(self):
        now = datetime.now(timezone.utc)

        snapshots_purged = []
        for slug, expires in self._snapshots_expiry.copy().items():
            if expires < now:
                if await self._purge_snapshot(slug):
                    snapshots_purged.append(slug)

        if len(snapshots_purged) == 1:
            _LOGGER.info("Purged 1 snapshot; %s", snapshots_purged[0])
        elif len(snapshots_purged) > 1:
            _LOGGER.info(
                "Purged %s snapshots; %s",
                len(snapshots_purged),
                tuple(snapshots_purged),
            )

    async def _purge_snapshot(self, slug):
        _LOGGER.debug("Attempting to remove snapshot: %s", slug)
        command = COMMAND_SNAPSHOT_REMOVE.format(slug=slug)

        try:
            result = await self._hassio.send_command(command, timeout=300)

            _LOGGER.debug("Snapshot remove result: %s", result)

            # remove snapshot expiry.
            del self._snapshots_expiry[slug]
            # write snapshot expiry to storage.
            await self._snapshots_store.async_save(self._snapshots_expiry)

        except HassioAPIError as err:
            _LOGGER.error("Error on Hass.io API: %s", err)
            return False
        return True


# name: "AutoBackup 12:20 9/11/2019"
# addons:
#   - a0d7b954_grafana
#   - core_configurator
# folders:
#   - homeassistant
# keep_days: 0.001
