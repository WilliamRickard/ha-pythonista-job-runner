"""Config flow for Pythonista Job Runner integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .client import RunnerClient, RunnerClientError
from .const import (
    CONF_BASE_URL,
    CONF_CREATE_REPAIRS,
    CONF_NOTIFY_POLICY,
    CONF_NOTIFY_TARGET,
    CONF_NOTIFY_THROTTLE_SECONDS,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
    DEFAULT_BASE_URL,
    DEFAULT_NOTIFY_POLICY,
    DEFAULT_NOTIFY_TARGET,
    DEFAULT_NOTIFY_THROTTLE_SECONDS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NOTIFY_POLICY_ALL,
    NOTIFY_POLICY_FAILURES_ONLY,
    NOTIFY_POLICY_OFF,
)


class PythonistaRunnerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Pythonista Job Runner."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial setup flow for connection fields only."""
        return await self._show_connection_form(step_id="user", user_input=user_input)

    async def async_step_reconfigure(self, user_input=None):
        """Allow editing setup details without deleting the entry."""
        return await self._show_connection_form(step_id="reconfigure", user_input=user_input, reconfigure=True)

    async def _show_connection_form(self, *, step_id: str, user_input=None, reconfigure: bool = False):
        errors = {}
        if user_input is not None:
            client = RunnerClient(user_input[CONF_BASE_URL], user_input[CONF_TOKEN], user_input[CONF_VERIFY_SSL])
            try:
                await self.hass.async_add_executor_job(client.health)
            except RunnerClientError:
                errors["base"] = "cannot_connect"
            else:
                unique = user_input[CONF_BASE_URL].rstrip("/")
                await self.async_set_unique_id(unique)
                if reconfigure:
                    self._abort_if_unique_id_mismatch()
                    entry = self._get_reconfigure_entry()
                    new_data = dict(entry.data)
                    new_data.update(user_input)
                    self.hass.config_entries.async_update_entry(entry, data=new_data)
                    return self.async_abort(reason="reconfigure_successful")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Pythonista Job Runner", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                vol.Required(CONF_TOKEN, default=""): str,
                vol.Optional(CONF_VERIFY_SSL, default=True): bool,
            }
        )
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return PythonistaRunnerOptionsFlow(config_entry)


class PythonistaRunnerOptionsFlow(config_entries.OptionsFlow):
    """Handle operational tuning options for Pythonista Job Runner."""

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        """Options step with runtime tuning fields only."""
        if user_input is not None:
            interval = max(5, min(300, int(user_input[CONF_SCAN_INTERVAL])))
            throttle = max(0, min(86400, int(user_input[CONF_NOTIFY_THROTTLE_SECONDS])))
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: interval,
                    CONF_CREATE_REPAIRS: bool(user_input[CONF_CREATE_REPAIRS]),
                    CONF_NOTIFY_POLICY: user_input[CONF_NOTIFY_POLICY],
                    CONF_NOTIFY_TARGET: str(user_input[CONF_NOTIFY_TARGET]).strip(),
                    CONF_NOTIFY_THROTTLE_SECONDS: throttle,
                },
            )
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=self._entry.options.get(CONF_SCAN_INTERVAL, self._entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))): int,
                vol.Optional(CONF_CREATE_REPAIRS, default=self._entry.options.get(CONF_CREATE_REPAIRS, self._entry.data.get(CONF_CREATE_REPAIRS, True))): bool,
                vol.Optional(CONF_NOTIFY_POLICY, default=self._entry.options.get(CONF_NOTIFY_POLICY, DEFAULT_NOTIFY_POLICY)): vol.In(
                    [NOTIFY_POLICY_OFF, NOTIFY_POLICY_FAILURES_ONLY, NOTIFY_POLICY_ALL]
                ),
                vol.Optional(CONF_NOTIFY_TARGET, default=self._entry.options.get(CONF_NOTIFY_TARGET, DEFAULT_NOTIFY_TARGET)): str,
                vol.Optional(
                    CONF_NOTIFY_THROTTLE_SECONDS,
                    default=self._entry.options.get(CONF_NOTIFY_THROTTLE_SECONDS, DEFAULT_NOTIFY_THROTTLE_SECONDS),
                ): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
