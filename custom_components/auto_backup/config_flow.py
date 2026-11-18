"""Config flow for Auto Backup integration."""

import logging
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers import selector

from .helpers import is_backup
from .nas_backend import NasError, validate_config
from .nas_manager import config_from_options
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
        vol.Optional("nas_enabled", default=False): bool,
        vol.Optional("nas_server", default=""): str,
        vol.Optional("nas_share", default=""): str,
        vol.Optional("nas_folder", default=""): str,
        vol.Optional("nas_username", default=""): str,
        vol.Optional("nas_workgroup", default="WORKGROUP"): str,
        vol.Optional("nas_password", default=""): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Optional("nas_daily", default=7): vol.All(int, vol.Range(min=1, max=90)),
        vol.Optional("nas_weekly", default=4): vol.All(int, vol.Range(min=1, max=52)),
        vol.Optional("nas_monthly", default=2): vol.All(int, vol.Range(min=1, max=24)),
        vol.Optional("nas_keep_local", default=1): vol.All(
            int, vol.Range(min=1, max=20)
        ),
        vol.Optional("nas_manage_legacy", default=False): bool,
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the Auto Backup options."""
        errors = {}
        if user_input is not None:
            # Never send the saved password back as a suggested form value.
            user_input["nas_password"] = user_input.get(
                "nas_password"
            ) or self.config_entry.options.get("nas_password", "")
            if user_input.get("nas_enabled"):
                if not is_hassio(self.hass):
                    errors["base"] = "nas_requires_supervisor"
                else:
                    try:
                        validate_config(config_from_options(user_input))
                    except NasError:
                        errors["base"] = "invalid_nas_config"
            if not errors:
                return self.async_create_entry(data=user_input)

        suggested = dict(user_input or self.config_entry.options)
        suggested.pop("nas_password", None)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, suggested),
            errors=errors,
        )
