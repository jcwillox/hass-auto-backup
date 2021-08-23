from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType, EventType

from . import AutoBackup
from .const import (
    DOMAIN,
    EVENT_BACKUPS_PURGED,
    EVENT_BACKUP_SUCCESSFUL,
    EVENT_BACKUP_FAILED,
    EVENT_BACKUP_START,
    DATA_AUTO_BACKUP,
)

ATTR_LAST_FAILURE = "last_failure"
ATTR_PURGEABLE = "purgeable_backups"
ATTR_MONITORED = "monitored_backups"

DEFAULT_ICON = "mdi:package-variant-closed"
DEFAULT_NAME = "Auto Backup"


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
):
    """Set up Auto Backup sensors based on a config entry."""
    auto_backup = hass.data[DOMAIN][DATA_AUTO_BACKUP]
    async_add_entities([AutoBackupSensor(auto_backup)])


class AutoBackupSensor(Entity):
    def __init__(self, auto_backup: AutoBackup):
        self._auto_backup = auto_backup

        self._attributes = {}
        self._listeners = []

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        @callback
        def update(_):
            """Update sensor on backup events."""
            self.async_schedule_update_ha_state(True)

        @callback
        def backup_failed(event: EventType):
            """Store last failed and update sensor"""
            self._attributes[ATTR_LAST_FAILURE] = event.data.get(ATTR_NAME)
            self.async_schedule_update_ha_state(True)

        self._listeners = [
            self.hass.bus.async_listen(event, update)
            for event in (
                EVENT_BACKUP_START,
                EVENT_BACKUP_SUCCESSFUL,
                EVENT_BACKUPS_PURGED,
            )
        ]
        self._listeners.append(
            self.hass.bus.async_listen(EVENT_BACKUP_FAILED, backup_failed)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        for remove in self._listeners:
            remove()

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
        return DEFAULT_ICON

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return "pending backup(s)"

    @property
    def state(self):
        """Return the state of the entity."""
        return self._auto_backup.state

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._attributes

    async def async_update(self):
        self._attributes[ATTR_MONITORED] = self._auto_backup.monitored
        self._attributes[ATTR_PURGEABLE] = self._auto_backup.purgeable
