"""Sensor platform for Pythonista Job Runner integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensors from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            RunnerMetricSensor(coordinator, entry, "jobs_running", "running jobs"),
            RunnerMetricSensor(coordinator, entry, "jobs_queued", "queued jobs"),
            RunnerMetricSensor(coordinator, entry, "jobs_done", "completed jobs"),
            RunnerMetricSensor(coordinator, entry, "jobs_error", "failed jobs"),
            RunnerMetricSensor(coordinator, entry, "disk_free_bytes", "disk free", native_unit_of_measurement="B"),
        ]
    )


class RunnerMetricSensor(CoordinatorEntity, SensorEntity):
    """Coordinator-backed sensor for a runner stats key."""

    def __init__(self, coordinator, entry: ConfigEntry, key: str, label: str, native_unit_of_measurement: str | None = None) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Pythonista Job Runner {label}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = native_unit_of_measurement

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("stats", {}).get(self._key)
