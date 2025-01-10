from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .manager import AutoBackup
from .const import (
    DATA_AUTO_BACKUP,
    EVENT_BACKUP_START,
    EVENT_BACKUP_SUCCESSFUL,
    EVENT_BACKUP_FAILED,
)
from .helpers import get_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up Auto Backup sensors based on a config entry."""
    auto_backup = hass.data[DATA_AUTO_BACKUP]
    async_add_entities(
        [
            AutoBackupStatusSensor(entry, auto_backup),
            AutoBackupProblemSensor(entry, auto_backup),
        ]
    )


class AutoBackupBaseBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, auto_backup: AutoBackup):
        self._auto_backup = auto_backup
        self._attr_unique_id = self.entity_description.key
        self._attr_device_info = get_device_info(entry)


class AutoBackupStatusSensor(AutoBackupBaseBinarySensor):
    entity_description = BinarySensorEntityDescription(
        key="status",
        name="Backup status",
        device_class=BinarySensorDeviceClass.RUNNING,
    )

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        @callback
        def update(_):
            """Update sensor on backup events."""
            self.async_schedule_update_ha_state(True)

        for event in (EVENT_BACKUP_START, EVENT_BACKUP_SUCCESSFUL, EVENT_BACKUP_FAILED):
            self.async_on_remove(self.hass.bus.async_listen(event, update))

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._auto_backup.state > 0


class AutoBackupProblemSensor(RestoreEntity, AutoBackupBaseBinarySensor):
    entity_description = BinarySensorEntityDescription(
        key="problem",
        name="Successful",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_registry_enabled_default=False,
    )
    _attr_is_on = False

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._attr_is_on = state.state == STATE_ON

        @callback
        def backup_success(_):
            """Update sensor on backup events."""
            self._attr_is_on = False
            self.async_schedule_update_ha_state(True)

        @callback
        def backup_failure(_):
            """Update sensor on backup events."""
            self._attr_is_on = True
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_BACKUP_SUCCESSFUL, backup_success)
        )
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_BACKUP_FAILED, backup_failure)
        )
