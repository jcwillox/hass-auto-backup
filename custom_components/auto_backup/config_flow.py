"""Config flow for Auto Backup integration."""
import logging
import os

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from . import CONF_AUTO_PURGE, CONF_BACKUP_TIMEOUT
from .const import DOMAIN, DEFAULT_BACKUP_TIMEOUT

_LOGGER = logging.getLogger(__name__)


def validate_input():
    """Validate existence of Hass.io."""
    for env in ("HASSIO", "HASSIO_TOKEN"):
        if not os.environ.get(env):
            return False
    return True


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Auto Backup."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user")

        if self._async_current_entries():
            return self.async_abort(reason="single_instance")

        if not validate_input():
            return self.async_abort(reason="missing_hassio")

        return self.async_create_entry(title="Auto Backup", data=user_input)

    async def async_step_import(self, user_input=None):
        """Import a config entry from configuration.yaml."""
        _LOGGER.info("Importing config entry from configuration.yaml")
        backup_timeout = user_input.get(CONF_BACKUP_TIMEOUT)
        if backup_timeout:
            user_input[CONF_BACKUP_TIMEOUT] = backup_timeout / 60

        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        """Initialize Auto Backup options flow."""
        self.config_entry: config_entries.ConfigEntry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Auto Backup options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # migrate option from data
        if self.config_entry.data:
            _LOGGER.info("Migrating data to options")
            data = self.config_entry.data
            self.hass.config_entries.async_update_entry(
                entry=self.config_entry, data={}, options=data
            )
        else:
            data = self.config_entry.options

        auto_purge = data.get(CONF_AUTO_PURGE, True)
        backup_timeout = data.get(CONF_BACKUP_TIMEOUT, DEFAULT_BACKUP_TIMEOUT)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_AUTO_PURGE, default=auto_purge): bool,
                    vol.Optional(CONF_BACKUP_TIMEOUT, default=backup_timeout): int,
                }
            ),
        )
