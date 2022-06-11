from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up Auto Backup sensors based on a config entry."""
    auto_backup = hass.data[DOMAIN][DATA_AUTO_BACKUP]
    async_add_entities([AutoBackupSensor(entry, auto_backup)])


class AutoBackupSensor(SensorEntity):
    entity_description = SensorEntityDescription(
        key="backups",
        icon="mdi:package-variant-closed",
        name="Auto Backup",
        native_unit_of_measurement="pending backup(s)",
    )

    _attr_unique_id = "sensor-auto-backup"
    _attr_extra_state_attributes = {}

    def __init__(self, entry: ConfigEntry, auto_backup: AutoBackup):
        self._auto_backup = auto_backup
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://jcwillox.github.io/hass-auto-backup",
            manufacturer="Auto Backup",
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        @callback
        def update(_):
            """Update sensor on backup events."""
            self.async_schedule_update_ha_state(True)

        @callback
        def backup_failed(event_: EventType):
            """Store last failed and update sensor"""
            self._attr_extra_state_attributes[ATTR_LAST_FAILURE] = event_.data.get(
                ATTR_NAME
            )
            self.async_schedule_update_ha_state(True)

        for event in (
            EVENT_BACKUP_START,
            EVENT_BACKUP_SUCCESSFUL,
            EVENT_BACKUPS_PURGED,
        ):
            self.async_on_remove(self.hass.bus.async_listen(event, update))
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_BACKUP_FAILED, backup_failed)
        )

    @property
    def native_value(self):
        """Return the state of the entity."""
        return self._auto_backup.state

    async def async_update(self):
        self._attr_extra_state_attributes[ATTR_MONITORED] = self._auto_backup.monitored
        self._attr_extra_state_attributes[ATTR_PURGEABLE] = self._auto_backup.purgeable
