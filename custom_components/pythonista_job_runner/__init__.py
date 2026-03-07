"""Home Assistant integration for Pythonista Job Runner."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .client import RunnerClient, RunnerClientError
from .const import CONF_BASE_URL, CONF_CREATE_REPAIRS, CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_VERIFY_SSL, DOMAIN
from .coordinator import PythonistaRunnerCoordinator
from .repairs import clear_issues, create_auth_issue, create_unreachable_issue
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pythonista Job Runner from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    base_url = entry.data[CONF_BASE_URL]
    token = entry.data.get(CONF_TOKEN, "")
    verify_ssl = bool(entry.data.get(CONF_VERIFY_SSL, True))
    scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, 15)))
    create_repairs = bool(entry.options.get(CONF_CREATE_REPAIRS, entry.data.get(CONF_CREATE_REPAIRS, True)))

    client = RunnerClient(base_url=base_url, token=token, verify_ssl=verify_ssl)
    coordinator = PythonistaRunnerCoordinator(hass, client, scan_interval)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as exc:
        if create_repairs:
            detail = str(exc)
            if "401" in detail or "403" in detail:
                create_auth_issue(hass, entry.entry_id, detail)
            else:
                create_unreachable_issue(hass, entry.entry_id, detail)
        raise ConfigEntryNotReady from exc

    clear_issues(hass, entry.entry_id)
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "base_url": base_url,
    }

    await async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up component root."""
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Cleanup issues when removing an entry."""
    clear_issues(hass, entry.entry_id)
