from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.components.backup.const import DOMAIN as DOMAIN_BACKUP
from homeassistant.loader import bind_hass

from .const import DOMAIN


@callback
@bind_hass
def is_backup(hass: HomeAssistant) -> bool:
    """Return true if backup integration is loaded.

    Async friendly.
    """
    return DOMAIN_BACKUP in hass.config.components


def get_device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://jcwillox.github.io/hass-auto-backup",
        manufacturer="Auto Backup",
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
    )
