from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import AutoBackup

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

PLATFORMS = [Platform.SENSOR]
