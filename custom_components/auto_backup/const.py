from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .manager import AutoBackup

DOMAIN = "auto_backup"
DATA_AUTO_BACKUP: HassKey[AutoBackup] = HassKey(DOMAIN)
UNSUB_LISTENER = "unsub_listener"

CONF_AUTO_PURGE = "auto_purge"
CONF_BACKUP_TIMEOUT = "backup_timeout"

DEFAULT_BACKUP_TIMEOUT_SECONDS = 1200
DEFAULT_BACKUP_TIMEOUT = 20

EVENT_BACKUP_SUCCESSFUL = f"{DOMAIN}.backup_successful"
EVENT_BACKUP_START = f"{DOMAIN}.backup_start"
EVENT_BACKUP_FAILED = f"{DOMAIN}.backup_failed"
EVENT_BACKUPS_PURGED = f"{DOMAIN}.purged_backups"

STORAGE_KEY = "snapshots_expiry"
STORAGE_VERSION = 1

ATTR_KEEP_DAYS = "keep_days"
ATTR_INCLUDE = "include"
ATTR_INCLUDE_ADDONS = "include_addons"
ATTR_INCLUDE_FOLDERS = "include_folders"
ATTR_EXCLUDE = "exclude"
ATTR_EXCLUDE_ADDONS = "exclude_addons"
ATTR_EXCLUDE_FOLDERS = "exclude_folders"
ATTR_DOWNLOAD_PATH = "download_path"
ATTR_COMPRESSED = "compressed"
ATTR_ENCRYPTED = "encrypted"
ATTR_LOCATION = "location"

ATTR_LAST_FAILURE = "last_failure"
ATTR_PURGEABLE = "purgeable_backups"
ATTR_MONITORED = "monitored_backups"
ATTR_ERROR = "error"
ATTR_SLUG = "slug"

DEFAULT_BACKUP_FOLDERS = {
    "ssl": "ssl",
    "share": "share",
    "media": "media",
    "addons": "addons/local",
    "config": "homeassistant",
    "local add-ons": "addons/local",
    "home assistant configuration": "homeassistant",
}

SERVICE_PURGE = "purge"
SERVICE_BACKUP = "backup"
SERVICE_BACKUP_FULL = "backup_full"
SERVICE_BACKUP_PARTIAL = "backup_partial"
