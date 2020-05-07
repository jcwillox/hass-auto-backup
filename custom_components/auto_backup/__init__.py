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
    SERVICE_SNAPSHOT_FULL,
    SERVICE_SNAPSHOT_PARTIAL,
    SCHEMA_SNAPSHOT_FULL,
    SCHEMA_SNAPSHOT_PARTIAL,
    ATTR_FOLDERS,
    ATTR_ADDONS,
    ATTR_PASSWORD,
)
from homeassistant.components.hassio.const import X_HASSIO
from homeassistant.components.hassio.handler import HassioAPIError
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

CHUNK_SIZE = 64 * 1024  # 64 KB

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
            vol.Optional(ATTR_FOLDERS, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(ATTR_ADDONS, default=[]): vol.All(cv.ensure_list, [cv.string]),
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
    # Check local setup
    for env in ("HASSIO", "HASSIO_TOKEN"):
        if os.environ.get(env):
            continue
        _LOGGER.error(
            "Missing %s environment variable. Please check you have Hass.io installed!",
            env,
        )
        return False

    web_session = hass.helpers.aiohttp_client.async_get_clientsession()

    config = config[DOMAIN]

    # initialise AutoBackup class.
    auto_backup = hass.data[DOMAIN] = AutoBackup(
        hass, web_session, config[CONF_AUTO_PURGE], config[CONF_BACKUP_TIMEOUT]
    )
    await auto_backup.load_snapshots_expiry()

    # load the auto backup sensor.
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("sensor", DOMAIN, {}, config)
    )

    # register services.
    async def snapshot_service_handler(call: ServiceCallType):
        """Handle Snapshot Creation Service Calls."""
        hass.async_create_task(
            auto_backup.new_snapshot(
                call.data.copy(), call.service == SERVICE_SNAPSHOT_FULL
            )
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
        web_session,
        auto_purge: bool,
        backup_timeout: int,
    ):
        self._hass = hass
        self.web_session = web_session
        self._ip = os.environ["HASSIO"]
        self._auto_purge = auto_purge
        self._backup_timeout = backup_timeout

        self._snapshots_store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{STORAGE_KEY}", encoder=JSONEncoder
        )
        self._snapshots_expiry = {}

        self._pending_snapshots = 0
        self.last_failure = None
        self.update_sensor_callback = None

    async def load_snapshots_expiry(self):
        """Load snapshots expiry dates from home assistants storage."""
        data = await self._snapshots_store.async_load()

        if data is not None:
            for slug, expiry in data.items():
                self._snapshots_expiry[slug] = datetime.fromisoformat(expiry)

    async def get_addons(self, only_installed=True):
        """Retrieve a list of addons from Hass.io."""
        try:
            result = await self.send_command(COMMAND_GET_ADDONS, method="get")

            addons = result.get("data", {}).get("addons")
            if addons is None:
                raise HassioAPIError("No addons were returned.")

            if only_installed:
                return [addon for addon in addons if addon["installed"]]
            return addons

        except HassioAPIError as err:
            _LOGGER.error("Failed to retrieve addons: %s", err)

        return None

    @property
    def snapshots_expiry(self):
        return self._snapshots_expiry

    @property
    def pending_snapshots(self):
        return self._pending_snapshots

    async def _replace_addon_names(self, snapshot_addons, addons=None):
        """Replace addon names with their appropriate slugs."""
        if not addons:
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

                # append addons.
                addons = await self.get_addons()
                if addons:
                    excluded_addons = await self._replace_addon_names(
                        exclude[ATTR_ADDONS], addons
                    )

                    data[ATTR_ADDONS] = [
                        addon["slug"]
                        for addon in addons
                        if addon["slug"] not in excluded_addons
                    ]

                # append folders.
                excluded_folders = self._replace_folder_names(exclude[ATTR_FOLDERS])
                data[ATTR_FOLDERS] = [
                    folder
                    for folder in DEFAULT_SNAPSHOT_FOLDERS.values()
                    if folder not in excluded_folders
                ]

        else:
            # performing partial backup.
            # replace addon names with their appropriate slugs.
            if ATTR_ADDONS in data:
                data[ATTR_ADDONS] = await self._replace_addon_names(data[ATTR_ADDONS])
            # replace friendly folder names.
            if ATTR_FOLDERS in data:
                data[ATTR_FOLDERS] = self._replace_folder_names(data[ATTR_FOLDERS])

        # ensure password is scrubbed from logs.
        password = data.get(ATTR_PASSWORD)
        if password:
            data[ATTR_PASSWORD] = "<hidden>"

        _LOGGER.debug(
            "New snapshot; command: %s, keep_days: %s, data: %s, timeout: %s",
            command,
            keep_days,
            data,
            self._backup_timeout,
        )

        # re-add password if it existed.
        if password:
            data[ATTR_PASSWORD] = password
            del password  # remove from memory

        # add to pending snapshots and update sensor.
        self._pending_snapshots += 1
        if self.update_sensor_callback:
            self.update_sensor_callback()

        # make request to create new snapshot.
        try:
            result = await self.send_command(
                command, payload=data, timeout=self._backup_timeout
            )

            _LOGGER.debug("Snapshot create result: %s" % result)

            slug = result.get("data", {}).get("slug")
            if slug is None:
                error = "There may be a backup already in progress."
                if data.get("message"):
                    error = f"{error} {data.get('message')}"
                raise HassioAPIError(error)

            # snapshot creation was successful
            _LOGGER.info(
                "Snapshot created successfully; '%s' (%s)", data[ATTR_NAME], slug
            )
            self._hass.bus.async_fire(
                f"{DOMAIN}.snapshot_successful", {"name": data[ATTR_NAME], "slug": slug}
            )

            if keep_days is not None:
                # set snapshot expiry
                self._snapshots_expiry[slug] = datetime.now(timezone.utc) + timedelta(
                    days=float(keep_days)
                )
                # write snapshot expiry to storage
                await self._snapshots_store.async_save(self._snapshots_expiry)

            # copy snapshot to location if specified
            if backup_path:
                await self.copy_snapshot(data[ATTR_NAME], slug, backup_path)

        except HassioAPIError as err:
            _LOGGER.error("Error during backup. %s", err)
            self._hass.bus.async_fire(
                f"{DOMAIN}.snapshot_failed",
                {"name": data[ATTR_NAME], "error": str(err)},
            )
            self.last_failure = data[ATTR_NAME]

        # remove from pending snapshots and update sensor.
        self._pending_snapshots -= 1
        if self.update_sensor_callback:
            self.update_sensor_callback()

        # purging old snapshots
        if self._auto_purge:
            await self.purge_snapshots()

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

        if len(snapshots_purged) > 0:
            self._hass.bus.async_fire(
                f"{DOMAIN}.purged_snapshots", {"snapshots": snapshots_purged}
            )

            # update sensor after purge.
            if self.update_sensor_callback:
                self.update_sensor_callback()
        else:
            _LOGGER.debug("No snapshots required purging.")

    async def _purge_snapshot(self, slug):
        """Purge an individual snapshot from Hass.io."""
        _LOGGER.debug("Attempting to remove snapshot: %s", slug)
        command = COMMAND_SNAPSHOT_REMOVE.format(slug=slug)

        try:
            result = await self.send_command(command, timeout=300)

            if result["result"] == "error":
                _LOGGER.debug("Purge result: %s", result)
                _LOGGER.warning(
                    "Issue purging snapshot (%s), assuming it was already deleted.",
                    slug,
                )

            # remove snapshot expiry.
            del self._snapshots_expiry[slug]
            # write snapshot expiry to storage.
            await self._snapshots_store.async_save(self._snapshots_expiry)

        except HassioAPIError as err:
            _LOGGER.error("Failed to purge snapshot: %s", err)
            return False
        return True

    async def copy_snapshot(self, name, slug, backup_path):
        """Download snapshot to the specified location."""

        # ensure the name is a valid filename.
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

    async def download_snapshot(self, slug, output_path):
        """Download and save a snapshot from Hass.io."""
        command = COMMAND_SNAPSHOT_DOWNLOAD.format(slug=slug)

        try:
            with async_timeout.timeout(self._backup_timeout):
                request = await self.web_session.request(
                    "get",
                    f"http://{self._ip}{command}",
                    headers={X_HASSIO: os.environ.get("HASSIO_TOKEN", "")},
                    timeout=None,
                )

                if request.status not in (200, 400):
                    _LOGGER.error("%s return code %d.", command, request.status)
                    raise HassioAPIError()

                with open(output_path, "wb") as file:
                    while True:
                        chunk = await request.content.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        file.write(chunk)

                _LOGGER.info("Downloaded snapshot '%s' to '%s'", slug, output_path)
                return

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout on %s request", command)

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on %s request %s", command, err)

        except IOError:
            _LOGGER.error("Failed to download snapshot '%s' to '%s'", slug, output_path)

        raise HassioAPIError(
            "Snapshot download failed. Check the logs for more information."
        )

    async def send_command(self, command, method="post", payload=None, timeout=10):
        """Send API command to Hass.io.

        This method is a coroutine.
        """
        try:
            with async_timeout.timeout(timeout):
                request = await self.web_session.request(
                    method,
                    f"http://{self._ip}{command}",
                    json=payload,
                    headers={X_HASSIO: os.environ.get("HASSIO_TOKEN", "")},
                    timeout=None,
                )

                if request.status not in (200, 400):
                    _LOGGER.error("%s return code %d.", command, request.status)
                    raise HassioAPIError()

                answer = await request.json()
                return answer

        except asyncio.TimeoutError:
            raise HassioAPIError("Timeout on %s request" % command)

        except aiohttp.ClientError as err:
            raise HassioAPIError("Client error on %s request %s" % (command, err))

        raise HassioAPIError("Failed to call %s" % command)
