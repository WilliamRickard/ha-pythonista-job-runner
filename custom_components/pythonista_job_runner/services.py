"""Service registration for Pythonista Job Runner integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    DOMAIN,
    SERVICE_CANCEL_JOB,
    SERVICE_PURGE_DONE_JOBS,
    SERVICE_PURGE_FAILED_JOBS,
    SERVICE_PURGE_JOBS,
    SERVICE_REFRESH,
)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    async def _purge(call: ServiceCall) -> None:
        entry_id = call.data["entry_id"]
        states = call.data.get("states", [])
        older_than_hours = int(call.data.get("older_than_hours", 0))
        dry_run = bool(call.data.get("dry_run", False))
        entry_data = hass.data[DOMAIN][entry_id]
        await hass.async_add_executor_job(entry_data["client"].purge, states, older_than_hours, dry_run)
        await entry_data["coordinator"].async_request_refresh()

    async def _purge_predefined(call: ServiceCall, states: list[str]) -> None:
        entry_id = call.data["entry_id"]
        older_than_hours = int(call.data.get("older_than_hours", 0))
        dry_run = bool(call.data.get("dry_run", False))
        entry_data = hass.data[DOMAIN][entry_id]
        await hass.async_add_executor_job(entry_data["client"].purge, states, older_than_hours, dry_run)
        await entry_data["coordinator"].async_request_refresh()

    async def _refresh(call: ServiceCall) -> None:
        entry_data = hass.data[DOMAIN][call.data["entry_id"]]
        await entry_data["coordinator"].async_request_refresh()

    async def _cancel(call: ServiceCall) -> None:
        entry_data = hass.data[DOMAIN][call.data["entry_id"]]
        await hass.async_add_executor_job(entry_data["client"].cancel, call.data["job_id"])
        await entry_data["coordinator"].async_request_refresh()

    if hass.services.has_service(DOMAIN, SERVICE_PURGE_JOBS):
        return

    common_schema = vol.Schema({vol.Required("entry_id"): str, vol.Optional("older_than_hours", default=0): int, vol.Optional("dry_run", default=False): bool})

    hass.services.async_register(
        DOMAIN,
        SERVICE_PURGE_JOBS,
        _purge,
        schema=vol.Schema(
            {
                vol.Required("entry_id"): str,
                vol.Optional("states", default=[]): [str],
                vol.Optional("older_than_hours", default=0): int,
                vol.Optional("dry_run", default=False): bool,
            }
        ),
    )
    async def _purge_done(call: ServiceCall) -> None:
        await _purge_predefined(call, ["done"])

    async def _purge_failed(call: ServiceCall) -> None:
        await _purge_predefined(call, ["error"])

    hass.services.async_register(DOMAIN, SERVICE_PURGE_DONE_JOBS, _purge_done, schema=common_schema)
    hass.services.async_register(DOMAIN, SERVICE_PURGE_FAILED_JOBS, _purge_failed, schema=common_schema)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _refresh, schema=vol.Schema({vol.Required("entry_id"): str}))
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_JOB,
        _cancel,
        schema=vol.Schema({vol.Required("entry_id"): str, vol.Required("job_id"): str}),
    )
