"""Service registration for Pythonista Job Runner integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN


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

    if hass.services.has_service(DOMAIN, "purge_jobs"):
        return

    hass.services.async_register(
        DOMAIN,
        "purge_jobs",
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
