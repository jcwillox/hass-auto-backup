from datetime import datetime, timezone

from homeassistant.helpers import entity
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from . import DOMAIN, AutoBackup

DEFAULT_NAME = "Auto Backup"


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up the Sensor."""
    if discovery_info is None:
        return

    async_add_entities([AutoBackupSensor(hass, config)])


class AutoBackupSensor(entity.Entity):
    def __init__(self, hass: HomeAssistantType, config: ConfigType):
        self._config = config

        self.auto_backup: AutoBackup = hass.data[DOMAIN]
        self.auto_backup.update_sensor_callback = self.update_callback

        self._state = 0
        self._attributes = {}

    def update_callback(self):
        """Force sensor to update, for timely state changes."""
        self.async_schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the entity."""
        return DEFAULT_NAME

    @property
    def unique_id(self):
        return "sensor-auto-backup"

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:package-variant-closed"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return "pending backup(s)"

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    async def async_update(self):
        self._state = self.auto_backup.pending_snapshots

        self._attributes = {
            "monitored_snapshots": len(self.auto_backup.snapshots_expiry),
            "purgeable_snapshots": self.get_purgeable_snapshots(),
        }
        if self.auto_backup.last_failure:
            self._attributes["last_failure"] = self.auto_backup.last_failure

    def get_purgeable_snapshots(self):
        now = datetime.now(timezone.utc)

        purgeable = 0
        for expires in self.auto_backup.snapshots_expiry.values():
            if expires < now:
                purgeable += 1

        return purgeable
