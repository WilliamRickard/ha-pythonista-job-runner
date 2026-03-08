"""Event entities exposing stable job lifecycle automation surfaces."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import EVENT_JOB_COMPLETED, EVENT_JOB_FAILED, EVENT_JOB_STARTED


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up event entities."""
    entities = [
        RunnerLifecycleEventEntity(hass, entry, "job_started", EVENT_JOB_STARTED),
        RunnerLifecycleEventEntity(hass, entry, "job_completed", EVENT_JOB_COMPLETED),
        RunnerLifecycleEventEntity(hass, entry, "job_failed", EVENT_JOB_FAILED),
    ]
    async_add_entities(entities)


class RunnerLifecycleEventEntity(EventEntity):
    """Mirror a Home Assistant bus event into an EventEntity trigger surface."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, key: str, bus_event: str) -> None:
        self.hass = hass
        self._entry = entry
        self._key = key
        self._bus_event = bus_event
        self._unsub: CALLBACK_TYPE | None = None
        self._attr_name = f"Pythonista Runner {key.replace('_', ' ')}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to bus event."""
        @callback
        def _handle(event: Event) -> None:
            payload = dict(event.data or {})
            self._trigger_event(event_type=self._key, event_attributes=payload)

        self._unsub = self.hass.bus.async_listen(self._bus_event, _handle)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from bus event."""
        if self._unsub:
            self._unsub()
            self._unsub = None
