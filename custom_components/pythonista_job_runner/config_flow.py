"""Config flow for Pythonista Job Runner integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .client import RunnerClient, RunnerClientError
from .const import CONF_BASE_URL, CONF_CREATE_REPAIRS, CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_VERIFY_SSL, DEFAULT_BASE_URL, DEFAULT_SCAN_INTERVAL, DOMAIN


class PythonistaRunnerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Pythonista Job Runner."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            client = RunnerClient(user_input[CONF_BASE_URL], user_input[CONF_TOKEN], user_input[CONF_VERIFY_SSL])
            try:
                await self.hass.async_add_executor_job(client.health)
            except RunnerClientError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_BASE_URL].rstrip("/"))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Pythonista Job Runner", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                vol.Required(CONF_TOKEN, default=""): str,
                vol.Optional(CONF_VERIFY_SSL, default=True): bool,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                vol.Optional(CONF_CREATE_REPAIRS, default=True): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        return await self.async_step_user(user_input)

    @staticmethod
    def async_get_options_flow(config_entry):
        return PythonistaRunnerOptionsFlow(config_entry)


class PythonistaRunnerOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Pythonista Job Runner."""

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=self._entry.options.get(CONF_SCAN_INTERVAL, self._entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))): int,
                vol.Optional(CONF_CREATE_REPAIRS, default=self._entry.options.get(CONF_CREATE_REPAIRS, self._entry.data.get(CONF_CREATE_REPAIRS, True))): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
