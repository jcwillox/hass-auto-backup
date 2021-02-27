DOMAIN = "auto_backup"
DATA_AUTO_BACKUP = "auto_backup"
UNSUB_LISTENER = "unsub_listener"

CONF_AUTO_PURGE = "auto_purge"
CONF_BACKUP_TIMEOUT = "backup_timeout"

DEFAULT_BACKUP_TIMEOUT_SECONDS = 1200
DEFAULT_BACKUP_TIMEOUT = 20

EVENT_SNAPSHOT_SUCCESSFUL = f"{DOMAIN}.snapshot_successful"
EVENT_SNAPSHOT_START = f"{DOMAIN}.snapshot_start"
EVENT_SNAPSHOT_FAILED = f"{DOMAIN}.snapshot_failed"
EVENT_SNAPSHOTS_PURGED = f"{DOMAIN}.purged_snapshots"
