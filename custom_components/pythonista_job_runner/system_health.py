"""System health support for Pythonista Job Runner integration."""

from __future__ import annotations

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_register(hass: HomeAssistant, register: system_health.SystemHealthRegistration) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict:
    """Return basic health details for the first configured entry."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        return {"configured": False}

    first = next(iter(entries.values()))
    coord = first["coordinator"]
    data = coord.data or {}
    stats = data.get("stats", {})
    return {
        "configured": True,
        "base_url": first["base_url"],
        "reachable": bool(data.get("health")),
        "jobs_running": stats.get("jobs_running"),
        "jobs_queued": stats.get("jobs_queued"),
        "jobs_error": stats.get("jobs_error"),
        "disk_free_bytes": stats.get("disk_free_bytes"),
    }
