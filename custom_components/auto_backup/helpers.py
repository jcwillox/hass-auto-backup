from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN


def get_device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://jcwillox.github.io/hass-auto-backup",
        manufacturer="Auto Backup",
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
    )
