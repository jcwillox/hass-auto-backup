from datetime import datetime
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    SensorDeviceClass,
    RestoreSensor,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    EVENT_BACKUPS_PURGED,
    EVENT_BACKUP_SUCCESSFUL,
    EVENT_BACKUP_FAILED,
    EVENT_BACKUP_START,
    DATA_AUTO_BACKUP,
    ATTR_LAST_FAILURE,
    ATTR_MONITORED,
    ATTR_PURGEABLE,
    ATTR_ERROR,
    ATTR_SLUG,
)
from .helpers import get_device_info
from .manager import AutoBackup


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up Auto Backup sensors based on a config entry."""
    auto_backup = hass.data[DATA_AUTO_BACKUP]
    async_add_entities(
        [
            AutoBackupSensor(entry, auto_backup),
            AutoBackupMonitoredSensor(entry, auto_backup),
            AutoBackupPurgeableSensor(entry, auto_backup),
            AutoBackupLastFailureSensor(entry, auto_backup),
            AutoBackupLastSuccessSensor(entry, auto_backup),
            AutoBackupNextExpirySensor(entry, auto_backup),
        ]
    )


class AutoBackupBaseSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, auto_backup: AutoBackup):
        self._auto_backup = auto_backup
        self._attr_unique_id = self.entity_description.key
        self._attr_device_info = get_device_info(entry)


class AutoBackupSensor(AutoBackupBaseSensor):
    entity_description = SensorEntityDescription(
        key="backups",
        name="Auto Backup",
        icon="mdi:package-variant-closed",
        native_unit_of_measurement="pending backup(s)",
    )
    _attr_extra_state_attributes = {}
    _attr_has_entity_name = False

    def __init__(self, entry: ConfigEntry, auto_backup: AutoBackup):
        super().__init__(entry, auto_backup)
        self._attr_unique_id = "sensor-auto-backup"

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        @callback
        def update(_):
            """Update sensor on backup events."""
            self.async_schedule_update_ha_state(True)

        @callback
        def backup_failed(event_: Event):
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


class AutoBackupMonitoredSensor(AutoBackupBaseSensor):
    entity_description = SensorEntityDescription(
        key="monitored",
        name="Monitored backups",
        icon="mdi:package-variant-closed-check",
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    )

    @property
    def native_value(self):
        """Return the state of the entity."""
        return self._auto_backup.monitored

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        @callback
        def update(_):
            """Update sensor on backup events."""
            self.async_schedule_update_ha_state(True)

        for event in (EVENT_BACKUP_SUCCESSFUL, EVENT_BACKUPS_PURGED):
            self.async_on_remove(self.hass.bus.async_listen(event, update))


class AutoBackupPurgeableSensor(AutoBackupBaseSensor):
    entity_description = SensorEntityDescription(
        key="purgeable",
        name="Purgeable backups",
        icon="mdi:package-variant-closed-remove",
        state_class=SensorStateClass.MEASUREMENT,
    )

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        @callback
        def update(_):
            """Update sensor on backup events."""
            self.async_schedule_update_ha_state(True)

        for event in (EVENT_BACKUP_SUCCESSFUL, EVENT_BACKUPS_PURGED):
            self.async_on_remove(self.hass.bus.async_listen(event, update))

    @property
    def native_value(self):
        """Return the state of the entity."""
        return self._auto_backup.purgeable


class AutoBackupLastFailureSensor(RestoreSensor, AutoBackupBaseSensor):
    entity_description = SensorEntityDescription(
        key="last-failure",
        name="Last failure",
        device_class=SensorDeviceClass.TIMESTAMP,
    )
    _attr_extra_state_attributes = {}
    _attr_should_poll = False

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        data = await self.async_get_last_sensor_data()
        if state and data:
            self._attr_native_value = data.native_value
            self._attr_extra_state_attributes[ATTR_NAME] = state.attributes.get(
                ATTR_NAME
            )
            self._attr_extra_state_attributes[ATTR_ERROR] = state.attributes.get(
                ATTR_ERROR
            )

        @callback
        def backup_failed(event_: Event):
            """Store last failed and update sensor"""
            self._attr_native_value = datetime.now().astimezone()
            self._attr_extra_state_attributes[ATTR_NAME] = event_.data.get(ATTR_NAME)
            self._attr_extra_state_attributes[ATTR_ERROR] = event_.data.get(ATTR_ERROR)
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_BACKUP_FAILED, backup_failed)
        )


class AutoBackupLastSuccessSensor(RestoreSensor, AutoBackupBaseSensor):
    entity_description = SensorEntityDescription(
        key="last-success",
        name="Last success",
        device_class=SensorDeviceClass.TIMESTAMP,
    )
    _attr_extra_state_attributes = {}
    _attr_should_poll = False

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        data = await self.async_get_last_sensor_data()
        if state and data:
            self._attr_native_value = data.native_value
            self._attr_extra_state_attributes[ATTR_NAME] = state.attributes.get(
                ATTR_NAME
            )
            self._attr_extra_state_attributes[ATTR_SLUG] = state.attributes.get(
                ATTR_SLUG
            )

        @callback
        def backup_success(event_: Event):
            """Store last success and update sensor"""
            self._attr_native_value = datetime.now().astimezone()
            self._attr_extra_state_attributes[ATTR_NAME] = event_.data.get(ATTR_NAME)
            self._attr_extra_state_attributes[ATTR_SLUG] = event_.data.get(ATTR_SLUG)
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_BACKUP_SUCCESSFUL, backup_success)
        )


class AutoBackupNextExpirySensor(RestoreSensor, AutoBackupBaseSensor):
    entity_description = SensorEntityDescription(
        key="next-expiration",
        name="Next expiration",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    )
    _attr_extra_state_attributes = {}

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        data = await self.async_get_last_sensor_data()
        if data:
            self._attr_native_value = data.native_value

        @callback
        def backup_success(_):
            """Next expiry might have changes so update sensor"""
            self.async_schedule_update_ha_state(True)

        for event in (EVENT_BACKUP_SUCCESSFUL, EVENT_BACKUPS_PURGED):
            self.async_on_remove(self.hass.bus.async_listen(event, backup_success))

    @property
    def native_value(self):
        """Return next expiry datetime."""
        return self._auto_backup.get_next_expiry()
