"""Component to create and automatically remove Home Assistant backups."""

import logging
from os import getenv

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.backup.const import DATA_MANAGER
from homeassistant.components.hassio import (
    ATTR_FOLDERS,
    ATTR_ADDONS,
    ATTR_PASSWORD,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.hassio import is_hassio

from .const import (
    ATTR_KEEP_DAYS,
    ATTR_DOWNLOAD_PATH,
    ATTR_COMPRESSED,
    ATTR_LOCATION,
    ATTR_EXCLUDE,
    ATTR_INCLUDE,
    ATTR_INCLUDE_ADDONS,
    ATTR_INCLUDE_FOLDERS,
    ATTR_EXCLUDE_ADDONS,
    ATTR_EXCLUDE_FOLDERS,
    SERVICE_BACKUP,
    SERVICE_BACKUP_FULL,
    SERVICE_BACKUP_PARTIAL,
    SERVICE_PURGE,
    CONF_AUTO_PURGE,
    CONF_BACKUP_TIMEOUT,
    DEFAULT_BACKUP_TIMEOUT,
    DATA_AUTO_BACKUP,
    DOMAIN,
    ATTR_ENCRYPTED,
)
from .handlers import SupervisorHandler, BackupHandler
from .helpers import is_backup
from .manager import AutoBackup

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

SCHEMA_BACKUP_BASE = vol.Schema(
    {
        vol.Optional(ATTR_NAME): vol.Any(None, cv.string),
        vol.Optional(ATTR_PASSWORD): vol.Any(None, cv.string),
        vol.Optional(ATTR_KEEP_DAYS): vol.Any(None, vol.Coerce(float)),
        vol.Optional(ATTR_DOWNLOAD_PATH): vol.All(cv.ensure_list, [cv.isdir]),
        vol.Optional(ATTR_ENCRYPTED, default=False): cv.boolean,
        vol.Optional(ATTR_COMPRESSED, default=True): cv.boolean,
        vol.Optional(ATTR_LOCATION): vol.All(
            cv.string, lambda v: None if v == "/backup" else v
        ),
    },
)

SCHEMA_LIST_STRING = vol.All(cv.ensure_list, [cv.string])

SCHEMA_ADDONS_FOLDERS = {
    vol.Optional(ATTR_FOLDERS, default=[]): SCHEMA_LIST_STRING,
    vol.Optional(ATTR_ADDONS, default=[]): SCHEMA_LIST_STRING,
}

SCHEMA_BACKUP_FULL = SCHEMA_BACKUP_BASE.extend(
    {vol.Optional(ATTR_EXCLUDE): SCHEMA_ADDONS_FOLDERS}
)

SCHEMA_BACKUP_PARTIAL = SCHEMA_BACKUP_BASE.extend(SCHEMA_ADDONS_FOLDERS)

SCHEMA_BACKUP = vol.Any(
    SCHEMA_BACKUP_BASE.extend(
        {
            vol.Optional(ATTR_INCLUDE): SCHEMA_ADDONS_FOLDERS,
            vol.Optional(ATTR_EXCLUDE): SCHEMA_ADDONS_FOLDERS,
        }
    ),
    SCHEMA_BACKUP_BASE.extend(
        {
            vol.Optional(ATTR_INCLUDE_ADDONS): SCHEMA_LIST_STRING,
            vol.Optional(ATTR_INCLUDE_FOLDERS): SCHEMA_LIST_STRING,
            vol.Optional(ATTR_EXCLUDE_ADDONS): SCHEMA_LIST_STRING,
            vol.Optional(ATTR_EXCLUDE_FOLDERS): SCHEMA_LIST_STRING,
        }
    ),
)

MAP_SERVICES = {
    SERVICE_BACKUP: SCHEMA_BACKUP,
    SERVICE_BACKUP_FULL: SCHEMA_BACKUP_FULL,
    SERVICE_BACKUP_PARTIAL: SCHEMA_BACKUP_PARTIAL,
    SERVICE_PURGE: None,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Auto Backup from a config entry."""
    _LOGGER.info("Setting up Auto Backup config entry %s", entry.entry_id)

    # check backup integration or supervisor is available
    if not is_hassio(hass) and not is_backup(hass):
        _LOGGER.error(
            "You must be running Home Assistant Supervised or have the 'backup' integration enabled."
        )
        return False

    options = {
        CONF_AUTO_PURGE: entry.options.get(CONF_AUTO_PURGE, True),
        CONF_BACKUP_TIMEOUT: entry.options.get(
            CONF_BACKUP_TIMEOUT, DEFAULT_BACKUP_TIMEOUT
        ),
    }

    if is_hassio(hass):
        handler = SupervisorHandler(getenv("SUPERVISOR"), async_get_clientsession(hass))
    else:
        handler = BackupHandler(hass, hass.data[DATA_MANAGER])

    auto_backup = AutoBackup(hass, options, handler)
    hass.data[DATA_AUTO_BACKUP] = auto_backup
    entry.async_on_unload(entry.add_update_listener(auto_backup.update_listener))

    await auto_backup.load_snapshots_expiry()

    ### REGISTER SERVICES ###
    async def async_service_handler(call: ServiceCall):
        """Handle Auto Backup service calls."""
        if call.service == SERVICE_PURGE:
            await auto_backup.purge_backups()
        else:
            data = call.data.copy()
            if call.service == SERVICE_BACKUP_PARTIAL:
                data[ATTR_INCLUDE] = {
                    ATTR_FOLDERS: data.pop(ATTR_FOLDERS, []),
                    ATTR_ADDONS: data.pop(ATTR_ADDONS, []),
                }
            elif call.service == SERVICE_BACKUP:
                if ATTR_INCLUDE_ADDONS in data or ATTR_INCLUDE_FOLDERS in data:
                    data[ATTR_INCLUDE] = {
                        ATTR_FOLDERS: data.pop(ATTR_INCLUDE_FOLDERS, []),
                        ATTR_ADDONS: data.pop(ATTR_INCLUDE_ADDONS, []),
                    }
                if ATTR_EXCLUDE_ADDONS in data or ATTR_EXCLUDE_FOLDERS in data:
                    data[ATTR_EXCLUDE] = {
                        ATTR_FOLDERS: data.pop(ATTR_EXCLUDE_FOLDERS, []),
                        ATTR_ADDONS: data.pop(ATTR_EXCLUDE_ADDONS, []),
                    }

            await auto_backup.async_create_backup(data)

    for service, schema in MAP_SERVICES.items():
        hass.services.async_register(DOMAIN, service, async_service_handler, schema)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    for service in MAP_SERVICES.keys():
        hass.services.async_remove(DOMAIN, service)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
