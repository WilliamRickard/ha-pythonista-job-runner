# Version: 0.3.0-system-health.1
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
    package_summary = data.get("package_summary", {})
    package_info = package_summary.get("summary", {}) if isinstance(package_summary, dict) else {}
    return {
        "configured": True,
        "base_url": first["base_url"],
        "reachable": bool(data.get("health")),
        "jobs_running": stats.get("jobs_running"),
        "jobs_queued": stats.get("jobs_queued"),
        "jobs_error": stats.get("jobs_error"),
        "disk_free_bytes": stats.get("disk_free_bytes"),
        "package_cache_private_bytes": package_info.get("cache_private_bytes", stats.get("package_cache_private_bytes")),
        "package_venv_count": package_info.get("venv_count", stats.get("package_venv_count")),
        "package_default_profile": package_info.get("default_profile", stats.get("package_profile_default")),
        "package_last_prune_status": package_info.get("last_prune_status", stats.get("package_cache_last_prune_status")),
    }
