"""Button entities for stateless operational runner actions."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up runner action buttons."""
    async_add_entities(
        [
            RunnerActionButton(hass, entry, "refresh_now", "refresh now", lambda d: d["coordinator"].async_request_refresh()),
            RunnerActionButton(hass, entry, "purge_completed", "purge completed jobs", lambda d: hass.async_add_executor_job(d["client"].purge, ["done"], 0, False)),
            RunnerActionButton(hass, entry, "purge_failed", "purge failed jobs", lambda d: hass.async_add_executor_job(d["client"].purge, ["error"], 0, False)),
            RunnerActionButton(hass, entry, "purge_all_history", "purge all job history", lambda d: hass.async_add_executor_job(d["client"].purge, [], 0, False)),
        ]
    )


class RunnerActionButton(ButtonEntity):
    """A one-shot button action against the runner API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, key: str, label: str, action: Callable) -> None:
        self.hass = hass
        self._entry = entry
        self._key = key
        self._action = action
        self._attr_name = f"Pythonista Runner {label}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    async def async_press(self) -> None:
        entry_data = self.hass.data[DOMAIN][self._entry.entry_id]
        await self._action(entry_data)
        await entry_data["coordinator"].async_request_refresh()
