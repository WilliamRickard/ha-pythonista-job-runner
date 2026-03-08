"""Text entities for runtime runner controls."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NOTIFY_TARGET, DEFAULT_NOTIFY_TARGET
from .runtime_entities import async_update_runtime_option, merged_option_value


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up text entities."""
    async_add_entities([RunnerNotifyTargetText(hass, entry)])


class RunnerNotifyTargetText(TextEntity):
    """Text entity for selecting optional notify target service."""

    _attr_native_min = 0
    _attr_native_max = 120

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_name = "Pythonista Runner notify target"
        self._attr_unique_id = f"{entry.entry_id}_notify_target"

    @property
    def native_value(self) -> str:
        return str(merged_option_value(self._entry, CONF_NOTIFY_TARGET, DEFAULT_NOTIFY_TARGET))

    async def async_set_value(self, value: str) -> None:
        await async_update_runtime_option(self.hass, self._entry, CONF_NOTIFY_TARGET, value.strip())
