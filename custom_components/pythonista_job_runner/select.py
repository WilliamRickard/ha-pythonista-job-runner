"""Select entities for runtime runner controls."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_NOTIFY_POLICY,
    DEFAULT_NOTIFY_POLICY,
    NOTIFY_POLICY_ALL,
    NOTIFY_POLICY_FAILURES_ONLY,
    NOTIFY_POLICY_OFF,
)
from .runtime_entities import async_update_runtime_option, merged_option_value


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up select entities."""
    async_add_entities([RunnerNotifyPolicySelect(hass, entry)])


class RunnerNotifyPolicySelect(SelectEntity):
    """Select entity for completion/failure notification policy."""

    _attr_options = [NOTIFY_POLICY_OFF, NOTIFY_POLICY_FAILURES_ONLY, NOTIFY_POLICY_ALL]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_name = "Pythonista Runner notify policy"
        self._attr_unique_id = f"{entry.entry_id}_notify_policy"

    @property
    def current_option(self) -> str:
        return str(merged_option_value(self._entry, CONF_NOTIFY_POLICY, DEFAULT_NOTIFY_POLICY))

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            raise ValueError(f"Invalid notify policy option: {option}")
        await async_update_runtime_option(self.hass, self._entry, CONF_NOTIFY_POLICY, option)
