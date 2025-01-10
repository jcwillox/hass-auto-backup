"""Config flow for Auto Backup integration."""

import logging
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.hassio import is_hassio

from .helpers import is_backup
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
        return OptionsFlowHandler()


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTO_PURGE, default=True): bool,
        vol.Required(CONF_BACKUP_TIMEOUT, default=DEFAULT_BACKUP_TIMEOUT): int,
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the Auto Backup options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
