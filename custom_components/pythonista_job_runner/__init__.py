"""Home Assistant integration for Pythonista Job Runner."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .client import RunnerClient
from .const import (
    CONF_BASE_URL,
    CONF_CREATE_REPAIRS,
    CONF_NOTIFY_POLICY,
    CONF_NOTIFY_TARGET,
    CONF_NOTIFY_THROTTLE_SECONDS,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
    DEFAULT_NOTIFY_POLICY,
    DEFAULT_NOTIFY_TARGET,
    DEFAULT_NOTIFY_THROTTLE_SECONDS,
    DOMAIN,
)
from .coordinator import PythonistaRunnerCoordinator
from .intents import register_intents
from .notifications import NotificationManager
from .repairs import clear_issues, create_auth_issue, create_unreachable_issue
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TEXT,
    Platform.BUTTON,
    Platform.UPDATE,
    Platform.EVENT,
    Platform.NOTIFY,
]


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
    notifier = NotificationManager(
        hass=hass,
        policy=str(entry.options.get(CONF_NOTIFY_POLICY, DEFAULT_NOTIFY_POLICY)),
        target=str(entry.options.get(CONF_NOTIFY_TARGET, DEFAULT_NOTIFY_TARGET)),
        throttle_seconds=int(entry.options.get(CONF_NOTIFY_THROTTLE_SECONDS, DEFAULT_NOTIFY_THROTTLE_SECONDS)),
    )
    coordinator.set_notification_manager(notifier)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as exc:  # noqa: BLE001
        if create_repairs:
            detail = str(exc)
            if "401" in detail or "403" in detail:
                create_auth_issue(hass, entry.entry_id, detail)
            else:
                create_unreachable_issue(hass, entry.entry_id, detail)
        raise ConfigEntryNotReady from exc

    unsub_backup_started = hass.bus.async_listen(
        "backup_started", lambda _: hass.async_create_task(_async_handle_backup_event(hass, "backup_started"))
    )
    unsub_backup_ended = hass.bus.async_listen(
        "backup_ended", lambda _: hass.async_create_task(_async_handle_backup_event(hass, "backup_ended"))
    )

    clear_issues(hass, entry.entry_id)
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "base_url": base_url,
        "intents": register_intents(hass),
        "backup_event_unsubs": [unsub_backup_started, unsub_backup_ended],
    }

    await async_register_services(hass)
    entry.async_on_unload(entry.add_update_listener(async_reload_on_entry_update))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_handle_backup_event(hass: HomeAssistant, event_name: str) -> None:
    """Best-effort backup event handler for pause/resume behavior."""
    for data in hass.data.get(DOMAIN, {}).values():
        client = data.get("client")
        if client is None:
            continue
        if event_name == "backup_started":
            await hass.async_add_executor_job(client.backup_pause)
        elif event_name == "backup_ended":
            await hass.async_add_executor_job(client.backup_resume)


async def async_reload_on_entry_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when setup or runtime options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry."""
    entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
    for unsub in entry_data.get("backup_event_unsubs", []):
        unsub()
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
