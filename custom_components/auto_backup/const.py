from homeassistant.const import Platform

DOMAIN = "auto_backup"
DATA_AUTO_BACKUP = "auto_backup"
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
