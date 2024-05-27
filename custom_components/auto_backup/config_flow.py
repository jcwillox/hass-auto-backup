"""Config flow for Auto Backup integration."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.hassio import is_hassio
from homeassistant.core import callback, HomeAssistant

from . import is_backup
from .const import DOMAIN, DEFAULT_BACKUP_TIMEOUT, CONF_AUTO_PURGE, CONF_BACKUP_TIMEOUT

_LOGGER = logging.getLogger(__name__)


def validate_input(hass: HomeAssistant):
    """Validate existence of Hass.io."""
    return is_hassio(hass) or is_backup(hass)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Auto Backup."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            if self._async_current_entries():
                return self.async_abort(reason="single_instance")

            if not validate_input(self.hass):
                return self.async_abort(reason="missing_service")

            return self.async_create_entry(title="Auto Backup", data=user_input)

        return self.async_show_form(step_id="user")

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

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AUTO_PURGE,
                        default=self.config_entry.options.get(CONF_AUTO_PURGE, True),
                    ): bool,
                    vol.Required(
                        CONF_BACKUP_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_BACKUP_TIMEOUT, DEFAULT_BACKUP_TIMEOUT
                        ),
                    ): int,
                }
            ),
        )
