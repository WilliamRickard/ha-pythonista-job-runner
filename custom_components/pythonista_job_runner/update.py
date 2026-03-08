"""Update entity for Pythonista Job Runner add-on visibility."""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .release import fetch_latest_release

RELEASE_REPO = "WilliamRickard/ha-pythonista-job-runner"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up update entities."""
    async_add_entities([RunnerUpdateEntity(hass, entry)])


class RunnerUpdateEntity(UpdateEntity):
    """Read-only update visibility for add-on version tracking."""

    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_name = "Pythonista Runner add-on update"
        self._attr_unique_id = f"{entry.entry_id}_addon_update"
        self._attr_installable = False
        self._attr_installed_version = None
        self._attr_latest_version = None
        self._attr_release_url = None
        self._attr_release_summary = None

    async def async_update(self) -> None:
        data = self.hass.data[DOMAIN][self._entry.entry_id]
        info = await self.hass.async_add_executor_job(data["client"].info)
        self._attr_installed_version = str(info.get("version") or "") or None

        release = await self.hass.async_add_executor_job(fetch_latest_release, RELEASE_REPO)
        self._attr_latest_version = release.latest_version
        self._attr_release_url = release.release_url
        self._attr_release_summary = release.summary

    async def async_install(self, version, backup, **kwargs):
        """Installation is not supported by this integration."""
        raise NotImplementedError("Install is not supported; update in Home Assistant add-on store.")
