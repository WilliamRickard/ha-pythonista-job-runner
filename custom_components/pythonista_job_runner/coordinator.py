"""Data update coordinator for Pythonista Job Runner."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import RunnerClient, RunnerClientError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, EVENT_JOB_FINISHED, EVENT_JOB_UPDATED

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
        self._last_states: dict[str, str] = {}

    async def _async_update_data(self) -> dict:
        try:
            health = await self.hass.async_add_executor_job(self.client.health)
            stats = await self.hass.async_add_executor_job(self.client.stats)
            jobs_payload = await self.hass.async_add_executor_job(self.client.jobs)
            jobs = jobs_payload.get("jobs", []) if isinstance(jobs_payload, dict) else []
            self._emit_job_events(jobs)
            return {"health": health, "stats": stats, "jobs": jobs}
        except RunnerClientError as exc:
            raise UpdateFailed(str(exc)) from exc

    def _emit_job_events(self, jobs: list[dict]) -> None:
        """Emit namespaced events for job updates and completion transitions."""
        seen: dict[str, str] = {}
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("job_id") or "")
            state = str(job.get("state") or "")
            if not job_id:
                continue
            seen[job_id] = state
            prev = self._last_states.get(job_id)
            if prev != state:
                self.hass.bus.async_fire(EVENT_JOB_UPDATED, {"job_id": job_id, "state": state, "previous_state": prev})
                if state in {"done", "error"}:
                    self.hass.bus.async_fire(EVENT_JOB_FINISHED, {"job_id": job_id, "state": state, "previous_state": prev, "exit_code": job.get("exit_code")})
        self._last_states = seen
