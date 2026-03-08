"""Number entities for runtime runner controls."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .runtime_entities import async_update_runtime_option, merged_option_value


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up number entities."""
    async_add_entities([RunnerScanIntervalNumber(hass, entry)])


class RunnerScanIntervalNumber(NumberEntity):
    """Number entity for coordinator polling interval tuning."""

    _attr_native_min_value = 5
    _attr_native_max_value = 300
    _attr_native_step = 1

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_name = "Pythonista Runner scan interval"
        self._attr_unique_id = f"{entry.entry_id}_scan_interval"

    @property
    def native_value(self) -> float:
        return float(merged_option_value(self._entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    async def async_set_native_value(self, value: float) -> None:
        await async_update_runtime_option(self.hass, self._entry, CONF_SCAN_INTERVAL, int(value))
