"""Notify platform for Pythonista Job Runner."""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up notify entity."""
    async_add_entities([RunnerNotifyEntity(entry)])


class RunnerNotifyEntity(NotifyEntity):
    """Notification target for manual operator messages related to runner jobs."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_name = "Pythonista Runner notify"
        self._attr_unique_id = f"{entry.entry_id}_notify"

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Support notify entity contract; automatic notifications are coordinator-driven."""
        return
