from homeassistant.const import ATTR_NAME
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType, ConfigType, EventType
from . import AutoBackup
from .const import (
    DOMAIN,
    EVENT_SNAPSHOTS_PURGED,
    EVENT_SNAPSHOT_SUCCESSFUL,
    EVENT_SNAPSHOT_FAILED,
    EVENT_SNAPSHOT_START,
)

ATTR_LAST_FAILURE = "last_failure"
ATTR_PURGEABLE = "purgeable_snapshots"
ATTR_MONITORED = "monitored_snapshots"

DEFAULT_ICON = "mdi:package-variant-closed"
DEFAULT_NAME = "Auto Backup"


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up the Sensor."""
    if discovery_info is None:
        return

    auto_backup = hass.data[DOMAIN]
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
            """Update sensor on snapshot events."""
            self.async_schedule_update_ha_state(True)

        @callback
        def snapshot_failed(event: EventType):
            """Store last failed and update sensor"""
            self._attributes[ATTR_LAST_FAILURE] = event.data.get(ATTR_NAME)
            self.async_schedule_update_ha_state(True)

        self._listeners = [
            self.hass.bus.async_listen(event, update)
            for event in (
                EVENT_SNAPSHOT_START,
                EVENT_SNAPSHOT_SUCCESSFUL,
                EVENT_SNAPSHOTS_PURGED,
            )
        ]
        self._listeners.append(
            self.hass.bus.async_listen(EVENT_SNAPSHOT_FAILED, snapshot_failed)
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
