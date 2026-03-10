# Version: 0.3.0-sensor.1
"""Sensor platform for Pythonista Job Runner integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory
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
            RunnerPackageSensor(
                coordinator,
                entry,
                "package_cache_size",
                "package cache size",
                lambda data: _package_summary_value(data, "cache_private_bytes"),
                native_unit_of_measurement="B",
            ),
            RunnerPackageSensor(
                coordinator,
                entry,
                "package_venv_count",
                "package reusable environments",
                lambda data: _package_summary_value(data, "venv_count"),
            ),
            RunnerPackageSensor(
                coordinator,
                entry,
                "package_last_prune_status",
                "package last prune status",
                lambda data: _package_summary_value(data, "last_prune_status"),
            ),
            RunnerPackageSensor(
                coordinator,
                entry,
                "package_default_profile",
                "package default profile",
                lambda data: _package_summary_value(data, "default_profile"),
            ),
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


class RunnerPackageSensor(CoordinatorEntity, SensorEntity):
    """Coordinator-backed diagnostic sensor for package subsystem state."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        key: str,
        label: str,
        extractor: Callable[[dict[str, Any]], Any],
        native_unit_of_measurement: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._extractor = extractor
        self._attr_name = f"Pythonista Job Runner {label}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = native_unit_of_measurement

    @property
    def native_value(self):
        value = self._extractor(self.coordinator.data or {})
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


def _package_summary_value(data: dict[str, Any], key: str) -> Any:
    """Return one flattened package-summary value from coordinator data."""
    payload = data.get("package_summary") or {}
    summary = payload.get("summary") or {}
    if key in summary:
        return summary.get(key)
    if key == "default_profile":
        return payload.get("default_profile") or summary.get("default_profile")
    return None
