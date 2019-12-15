"""Component to create and remove Hass.io snapshots."""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from os.path import join, isfile

import aiohttp
import async_timeout
import voluptuous as vol
from slugify import slugify

import homeassistant.helpers.config_validation as cv
from homeassistant.components.hassio import (
    DOMAIN as HASSIO_DOMAIN,
    SERVICE_SNAPSHOT_FULL,
    SERVICE_SNAPSHOT_PARTIAL,
    SCHEMA_SNAPSHOT_FULL,
    SCHEMA_SNAPSHOT_PARTIAL,
    ATTR_FOLDERS,
    ATTR_ADDONS,
)
from homeassistant.components.hassio.const import X_HASSIO
from homeassistant.components.hassio.handler import HassioAPIError, HassIO
from homeassistant.const import ATTR_NAME
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceCallType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "auto_backup"
STORAGE_KEY = "snapshots_expiry"
STORAGE_VERSION = 1

ATTR_KEEP_DAYS = "keep_days"
ATTR_EXCLUDE = "exclude"
ATTR_BACKUP_PATH = "backup_path"

DEFAULT_SNAPSHOT_FOLDERS = {
    "ssl": "ssl",
    "share": "share",
    "local add-ons": "addons/local",
    "home assistant configuration": "homeassistant",
}

CONF_AUTO_PURGE = "auto_purge"
CONF_BACKUP_TIMEOUT = "backup_timeout"

DEFAULT_BACKUP_TIMEOUT = 1200

SERVICE_PURGE = "purge"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Optional(CONF_AUTO_PURGE, default=True): cv.boolean,
            vol.Optional(
                CONF_BACKUP_TIMEOUT, default=DEFAULT_BACKUP_TIMEOUT
            ): vol.Coerce(int),
        }
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_SNAPSHOT_FULL = SCHEMA_SNAPSHOT_FULL.extend(
    {
        vol.Optional(ATTR_KEEP_DAYS): vol.Coerce(float),
        vol.Optional(ATTR_EXCLUDE): {
            vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
        },
        vol.Optional(ATTR_BACKUP_PATH): cv.isdir,
    }
)

SCHEMA_SNAPSHOT_PARTIAL = SCHEMA_SNAPSHOT_PARTIAL.extend(
    {
        vol.Optional(ATTR_KEEP_DAYS): vol.Coerce(float),
        vol.Optional(ATTR_BACKUP_PATH): cv.isdir,
    }
)

COMMAND_SNAPSHOT_FULL = "/snapshots/new/full"
COMMAND_SNAPSHOT_PARTIAL = "/snapshots/new/partial"
COMMAND_SNAPSHOT_REMOVE = "/snapshots/{slug}/remove"
COMMAND_SNAPSHOT_DOWNLOAD = "/snapshots/{slug}/download"
COMMAND_GET_ADDONS = "/addons"


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
    auto_backup = AutoBackup(
        hass, hassio, config[CONF_AUTO_PURGE], config[CONF_BACKUP_TIMEOUT]
    )
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
    def __init__(
        self,
        hass: HomeAssistantType,
        hassio: HassIO,
        auto_purge: bool,
        backup_timeout: int,
    ):
        self._hass = hass
        self._hassio = hassio
        self._snapshots_store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{STORAGE_KEY}", encoder=JSONEncoder
        )
        self._snapshots_expiry = {}
        self._auto_purge = auto_purge
        self._backup_timeout = backup_timeout

    async def load_snapshots_expiry(self):
        """Load snapshots expiry dates from home assistants storage."""
        data = await self._snapshots_store.async_load()

        if data is not None:
            for slug, expiry in data.items():
                self._snapshots_expiry[slug] = datetime.fromisoformat(expiry)

    async def get_addons(self, only_installed=True):
        """Retrieve a list of addons from Hass.io."""
        try:
            result = await self._hassio.send_command(COMMAND_GET_ADDONS, method="get")

            addons = result.get("data", {}).get("addons")
            if addons is None:
                raise HassioAPIError("No addons were returned.")

            if only_installed:
                return [addon for addon in addons if addon["installed"]]
            return addons

        except HassioAPIError as err:
            _LOGGER.error("Error on Hass.io API: %s", err)

        return None

    async def _replace_addon_names(self, snapshot_addons):
        """Replace addon names with their appropriate slugs."""
        addons = await self.get_addons()
        if addons:
            for addon in addons:
                for idx, snapshot_addon in enumerate(snapshot_addons):
                    # perform case insensitive match.
                    if snapshot_addon.casefold() == addon["name"].casefold():
                        snapshot_addons[idx] = addon["slug"]
        return snapshot_addons

    @staticmethod
    def _replace_folder_names(snapshot_folders):
        """Convert folder name to lower case and replace friendly folder names."""
        for idx, snapshot_folder in enumerate(snapshot_folders):
            snapshot_folder = snapshot_folder.lower()
            snapshot_folders[idx] = DEFAULT_SNAPSHOT_FOLDERS.get(
                snapshot_folder, snapshot_folder
            )

        return snapshot_folders

    async def new_snapshot(self, data, full=False):
        """Create a new snapshot in Hass.io."""
        if ATTR_NAME not in data:
            # provide a default name if none was supplied.
            data[ATTR_NAME] = datetime.now(self._hass.config.time_zone).strftime(
                "%A, %b %d, %Y"
            )

        _LOGGER.debug("Creating snapshot %s", data[ATTR_NAME])

        command = COMMAND_SNAPSHOT_FULL if full else COMMAND_SNAPSHOT_PARTIAL
        keep_days = data.pop(ATTR_KEEP_DAYS, None)
        backup_path = data.pop(ATTR_BACKUP_PATH, None)

        if full:
            # performing full backup.
            exclude = data.pop(ATTR_EXCLUDE, None)
            if exclude:
                # handle exclude config.
                command = COMMAND_SNAPSHOT_PARTIAL

                excluded_addons = exclude.get(ATTR_ADDONS, [])
                if excluded_addons:
                    addons = await self.get_addons()
                    if addons:
                        snapshot_addons = []
                        for addon in addons:
                            if (
                                addon["slug"] in excluded_addons
                                or addon["name"] in excluded_addons
                            ):
                                continue
                            snapshot_addons.append(addon["slug"])
                        data[ATTR_ADDONS] = snapshot_addons
                        data[ATTR_ADDONS] = snapshot_addons

                excluded_folders = exclude.get(ATTR_FOLDERS, [])
                if excluded_folders:
                    excluded_folders = self._replace_folder_names(excluded_folders)
                    folders = []
                    for folder in DEFAULT_SNAPSHOT_FOLDERS.values():
                        if folder not in excluded_folders:
                            folders.append(folder)
                    data[ATTR_FOLDERS] = folders
        else:
            # performing partial backup.
            # replace addon names with their appropriate slugs.
            if ATTR_ADDONS in data:
                data[ATTR_ADDONS] = await self._replace_addon_names(data[ATTR_ADDONS])
            # replace friendly folder names.
            if ATTR_FOLDERS in data:
                data[ATTR_FOLDERS] = self._replace_folder_names(data[ATTR_FOLDERS])

        _LOGGER.debug(
            "New snapshot; command: %s, keep_days: %s, data: %s",
            command,
            keep_days,
            data,
        )

        # make request to create new snapshot.
        try:
            result = await self._hassio.send_command(
                command, payload=data, timeout=self._backup_timeout
            )

            _LOGGER.debug("Snapshot create result: %s" % result)

            slug = result.get("data", {}).get("slug")
            if slug is None:
                raise HassioAPIError(
                    "Backup failed. There may be a backup already in progress."
                )

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

            # copy backup to location if specified
            if backup_path:
                # ensure the name is a valid filename.
                name = data[ATTR_NAME]
                if name:
                    filename = slugify(name, lowercase=False, separator="_")
                else:
                    filename = slug

                # ensure the filename is a tar file.
                if not filename.endswith(".tar"):
                    filename += ".tar"

                destination = join(backup_path, filename)

                # check if file already exists
                if isfile(destination):
                    destination = join(backup_path, f"{slug}.tar")

                await self.download_snapshot(slug, destination)

            # purging old snapshots
            if self._auto_purge:
                await self.purge_snapshots()

        except HassioAPIError as err:
            _LOGGER.error("Error on Hass.io API: %s", err)

    async def purge_snapshots(self):
        """Purge expired snapshots from Hass.io."""
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
        """Purge an individual snapshot from Hass.io."""
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

    async def download_snapshot(self, slug, output_path):
        """Download and save a snapshot from Hass.io."""
        command = COMMAND_SNAPSHOT_DOWNLOAD.format(slug=slug)

        try:
            with async_timeout.timeout(self._backup_timeout):
                request = await self._hassio.websession.request(
                    "get",
                    f"http://{self._hassio._ip}{command}",
                    headers={X_HASSIO: os.environ.get("HASSIO_TOKEN", "")},
                )

                if request.status not in (200, 400):
                    _LOGGER.error("%s return code %d.", command, request.status)
                    raise HassioAPIError()

                with open(output_path, "wb") as file:
                    file.write(await request.read())

                _LOGGER.info("Downloaded snapshot '%s' to '%s'", slug, output_path)
                return

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout on %s request", command)

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on %s request %s", command, err)

        except IOError:
            _LOGGER.error("Failed to download snapshot '%s' to '%s'", slug, output_path)

        raise HassioAPIError()
