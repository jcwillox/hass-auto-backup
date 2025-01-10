from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .manager import AutoBackup
from .const import DATA_AUTO_BACKUP
from .helpers import get_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up Auto Backup sensors based on a config entry."""
    auto_backup = hass.data[DATA_AUTO_BACKUP]
    async_add_entities([AutoBackupPurgeButton(entry, auto_backup)])


class AutoBackupPurgeButton(ButtonEntity):
    entity_description = ButtonEntityDescription(
        key="purge",
        name="Purge backups",
        icon="mdi:close-circle",
    )
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, auto_backup: AutoBackup):
        self._auto_backup = auto_backup
        self._attr_unique_id = self.entity_description.key
        self._attr_device_info = get_device_info(entry)

    async def async_press(self) -> None:
        """Purge backups."""
        await self._auto_backup.purge_backups()
