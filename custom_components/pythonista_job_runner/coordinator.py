"""Data update coordinator for Pythonista Job Runner."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import RunnerClient, RunnerClientError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PythonistaRunnerCoordinator(DataUpdateCoordinator[dict]):
    """Polls add-on stats endpoint for integration entities and health views."""

    def __init__(self, hass: HomeAssistant, client: RunnerClient, scan_interval_s: int = DEFAULT_SCAN_INTERVAL) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=max(5, int(scan_interval_s))),
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            health = await self.hass.async_add_executor_job(self.client.health)
            stats = await self.hass.async_add_executor_job(self.client.stats)
            return {"health": health, "stats": stats}
        except RunnerClientError as exc:
            raise UpdateFailed(str(exc)) from exc
