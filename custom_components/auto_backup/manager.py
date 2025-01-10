import logging
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
from os.path import join, isfile
from typing import List, Dict, Tuple, Optional

from homeassistant.components.backup.manager import DATA_MANAGER
from homeassistant.components.hassio import (
    ATTR_FOLDERS,
    ATTR_ADDONS,
    ATTR_PASSWORD,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, __version__
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from slugify import slugify

from .const import (
    DOMAIN,
    EVENT_BACKUP_FAILED,
    EVENT_BACKUPS_PURGED,
    EVENT_BACKUP_SUCCESSFUL,
    EVENT_BACKUP_START,
    CONF_AUTO_PURGE,
    CONF_BACKUP_TIMEOUT,
    STORAGE_KEY,
    STORAGE_VERSION,
    DEFAULT_BACKUP_FOLDERS,
    ATTR_INCLUDE,
    ATTR_EXCLUDE,
    ATTR_KEEP_DAYS,
    ATTR_DOWNLOAD_PATH,
    ATTR_ENCRYPTED,
)
from .handlers import HassioAPIError, HandlerBase

_LOGGER = logging.getLogger(__name__)


class AutoBackup:
    def __init__(self, hass: HomeAssistant, options: Dict, handler: HandlerBase):
        self._hass = hass
        self._handler = handler
        self._manager = hass.data[DATA_MANAGER]
        self._auto_purge = options[CONF_AUTO_PURGE]
        self._backup_timeout = options[CONF_BACKUP_TIMEOUT] * 60
        self._state = 0
        self._snapshots = {}
        self._supervised = is_hassio(hass)
        self._store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{STORAGE_KEY}", encoder=JSONEncoder
        )

    async def update_listener(self, hass, entry: ConfigEntry):
        """Handle options update."""
        self._auto_purge = entry.options[CONF_AUTO_PURGE]
        self._backup_timeout = entry.options[CONF_BACKUP_TIMEOUT] * 60

    async def load_snapshots_expiry(self):
        """Load snapshots expiry dates from Home Assistant's storage."""
        data = await self._store.async_load()

        if data is not None:
            for slug, expiry in data.items():
                self._snapshots[slug] = datetime.fromisoformat(expiry)

    @property
    def monitored(self):
        return len(self._snapshots)

    @property
    def purgeable(self):
        return len(self.get_purgeable_snapshots())

    @property
    def state(self):
        return self._state

    def get_next_expiry(self) -> datetime | None:
        """Return the next snapshot expiry date that has not expired"""
        return min(
            (
                expiry
                for expiry in self._snapshots.values()
                if expiry > datetime.now().astimezone()
            ),
            default=None,
        )

    @classmethod
    def ensure_slugs(
        cls, inclusion: Dict[str, List[str]], installed_addons: List[Dict]
    ) -> Tuple[List[str], List[str]]:
        """Helper method to slugify both the addon and folder sections"""
        addons = inclusion[ATTR_ADDONS]
        folders = inclusion[ATTR_FOLDERS]
        return (
            list(cls.ensure_addon_slugs(addons, installed_addons)),
            cls.ensure_folder_slugs(folders),
        )

    @staticmethod
    def ensure_addon_slugs(addons: List[str], installed_addons: List[Dict]):
        """Expand wildcards and replace addon names with their appropriate slugs."""
        if not addons:
            return []

        for addon in addons:
            matched = False
            for installed_addon in installed_addons:
                # perform case-insensitive match.
                if addon.casefold() == installed_addon["name"].casefold():
                    yield installed_addon["slug"]
                    matched = True
                if fnmatchcase(installed_addon["slug"], addon):
                    yield installed_addon["slug"]
                    matched = True
            if not matched:
                _LOGGER.warning("Addon '%s' does not exist", addon)
                yield addon

    @staticmethod
    def ensure_folder_slugs(folders: List[str]) -> List[str]:
        """Convert folder name to lower case and replace friendly folder names."""
        if not folders:
            return []

        def match_folder(folder):
            folder = folder.casefold()
            return DEFAULT_BACKUP_FOLDERS.get(folder, folder)

        return [match_folder(folder) for folder in folders]

    def generate_backup_name(self) -> str:
        if not self._supervised:
            return f"Core {__version__}"
        time_zone = dt_util.get_time_zone(self._hass.config.time_zone)
        return datetime.now(time_zone).strftime("%A, %b %d, %Y")

    def validate_backup_config(self, config: Dict):
        """Validate the backup config."""
        if not self._supervised:
            # allow `include` if it only contains the configuration
            if ATTR_INCLUDE in config and not config.get(ATTR_EXCLUDE):
                # ensure no addons were included
                if not config[ATTR_INCLUDE][ATTR_ADDONS]:
                    folders = config[ATTR_INCLUDE][ATTR_FOLDERS]
                    folders = self.ensure_folder_slugs(folders)
                    if folders == ["homeassistant"]:
                        del config[ATTR_INCLUDE]

            if ATTR_INCLUDE in config or ATTR_EXCLUDE in config:
                raise HomeAssistantError(
                    "Partial backups (e.g. include/exclude) are not supported on non-supervised installations."
                )

        if not config.get(ATTR_NAME):
            config[ATTR_NAME] = self.generate_backup_name()

    async def async_create_backup(self, data: Dict):
        """Identify actual type of backup to create and handle include/exclude options"""
        self.validate_backup_config(data)

        _LOGGER.debug("Creating backup '%s'", data[ATTR_NAME])

        include: Dict = data.pop(ATTR_INCLUDE, None)
        exclude: Dict = data.pop(ATTR_EXCLUDE, None)

        if not (include or exclude):
            # must be a full backup
            await self._async_create_backup(data)
        else:
            installed_addons = await self._handler.get_addons()

            _LOGGER.debug("Installed addons: %s", installed_addons)

            # default to include all addons and folders
            addons: List[str] = [addon["slug"] for addon in installed_addons]
            folders: List[str] = list(set(DEFAULT_BACKUP_FOLDERS.values()))

            if include:
                addons, folders = self.ensure_slugs(include, installed_addons)

                _LOGGER.debug("Including; addons: %s, folders: %s", addons, folders)

            if exclude:
                excluded_addons, excluded_folders = self.ensure_slugs(
                    exclude, installed_addons
                )

                addons = [addon for addon in addons if addon not in excluded_addons]
                folders = [
                    folder for folder in folders if folder not in excluded_folders
                ]

                _LOGGER.debug(
                    "Excluding; addons: %s, folders: %s",
                    excluded_addons,
                    excluded_folders,
                )
                _LOGGER.debug(
                    "Including (excluded); addons: %s, folders: %s", addons, folders
                )

            data[ATTR_ADDONS] = addons
            data[ATTR_FOLDERS] = folders
            await self._async_create_backup(data, partial=True)

        ### PURGE BACKUPS ###
        if self._auto_purge:
            await self.purge_backups()

    async def _async_create_backup(self, data: Dict, partial: bool = False):
        """Create backup, update state, fire events, download backup and purge old backups"""
        keep_days = data.pop(ATTR_KEEP_DAYS, None)
        download_paths: Optional[List[str]] = data.pop(ATTR_DOWNLOAD_PATH, None)

        # support default encryption key
        if (
            not data.get(ATTR_PASSWORD, "")
            and data.get(ATTR_ENCRYPTED)
            and self._manager
        ):
            data[ATTR_PASSWORD] = self._manager.config.data.create_backup.password
            del data[ATTR_ENCRYPTED]
        elif ATTR_ENCRYPTED in data:
            del data[ATTR_ENCRYPTED]

        ### LOG DEBUG INFO ###
        # ensure password is scrubbed from logs
        password = data.get(ATTR_PASSWORD)
        if password:
            data[ATTR_PASSWORD] = "<hidden>"

        _LOGGER.debug(
            "Creating backup (%s); keep_days: %s, timeout: %s, data: %s",
            "partial" if partial else "full",
            keep_days,
            self._backup_timeout,
            data,
        )

        # re-add password if it existed
        if password:
            data[ATTR_PASSWORD] = password
            del password

        ### CREATE BACKUP ###
        self._state += 1
        self._hass.bus.async_fire(EVENT_BACKUP_START, {"name": data[ATTR_NAME]})

        try:
            try:
                result = await self._handler.create_backup(
                    data, partial, timeout=self._backup_timeout
                )
            except HassioAPIError as err:
                raise HassioAPIError(
                    str(err) + ". There may be a backup already in progress."
                )

            # backup creation was successful
            slug = result["slug"]
            name = result.get(ATTR_NAME, data[ATTR_NAME])

            _LOGGER.info("Backup created successfully: '%s' (%s)", name, slug)

            self._state -= 1
            self._hass.bus.async_fire(
                EVENT_BACKUP_SUCCESSFUL, {"name": name, "slug": slug}
            )

            if keep_days is not None:
                # set snapshot expiry
                self._snapshots[slug] = datetime.now(timezone.utc) + timedelta(
                    days=float(keep_days)
                )
                # write snapshot expiry to storage
                await self._store.async_save(self._snapshots)

            # download backup to location if specified
            if download_paths:
                for download_path in download_paths:
                    self._hass.async_create_task(
                        self.async_download_backup(name, slug, download_path)
                    )

        except Exception as err:
            _LOGGER.error("Error during backup. %s", err)
            self._state -= 1
            self._hass.bus.async_fire(
                EVENT_BACKUP_FAILED,
                {"name": data[ATTR_NAME], "error": str(err)},
            )

    def get_purgeable_snapshots(self) -> List[str]:
        """Returns the slugs of purgeable snapshots."""
        now = datetime.now(timezone.utc)
        return [slug for slug, expires in self._snapshots.items() if expires < now]

    async def purge_backups(self):
        """Purge expired backups from the Supervisor."""
        purged = [
            slug
            for slug in self.get_purgeable_snapshots()
            if await self._purge_snapshot(slug)
        ]

        if purged:
            _LOGGER.info(
                "Purged %s backups: %s",
                len(purged),
                purged,
            )
            self._hass.bus.async_fire(EVENT_BACKUPS_PURGED, {"backups": purged})
            # write updated snapshots list to storage
            await self._store.async_save(self._snapshots)
        else:
            _LOGGER.debug("No backups required purging.")

    async def _purge_snapshot(self, slug):
        """Purge an individual snapshot from Hass.io."""
        _LOGGER.debug("Attempting to remove backup: %s", slug)
        try:
            await self._handler.remove_backup(slug)
        except HassioAPIError as err:
            message = "Failed to purge backup: %s, If it was intentionally moved or deleted externally you can ignore this error."
            if str(err) == "Backup does not exist":
                _LOGGER.warning(message, err)
            else:
                _LOGGER.error(message, err)
            return False
        finally:
            # remove snapshot expiry.
            del self._snapshots[slug]
        return True

    def async_download_backup(self, name, slug, backup_path):
        """Download backup to the specified location."""

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

        return self._handler.download_backup(
            slug, destination, timeout=self._backup_timeout
        )
