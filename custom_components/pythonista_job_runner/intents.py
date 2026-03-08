"""Assist intent handlers for Pythonista Job Runner."""

from __future__ import annotations

from homeassistant.helpers import intent

from .const import DOMAIN


class RunnerBaseIntent(intent.IntentHandler):
    """Base class for coordinator-backed runner intents."""

    slot_schema = {}
    platform = DOMAIN

    def _coordinator(self, hass):
        entries = hass.data.get(DOMAIN, {})
        if not entries:
            return None
        return next(iter(entries.values())).get("coordinator")


class RunnerJobsRunningIntent(RunnerBaseIntent):
    """Return running jobs count."""

    intent_type = "PythonistaRunnerJobsRunningIntent"
    description = "Get the number of running Pythonista jobs"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        response = intent_obj.create_response()
        coordinator = self._coordinator(intent_obj.hass)
        running = int(((coordinator.data or {}).get("stats") or {}).get("jobs_running", 0)) if coordinator else 0
        response.async_set_speech(f"There are {running} running Pythonista jobs.")
        return response


class RunnerQueueDepthIntent(RunnerBaseIntent):
    """Return queued jobs count."""

    intent_type = "PythonistaRunnerQueueDepthIntent"
    description = "Get the Pythonista queue depth"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        response = intent_obj.create_response()
        coordinator = self._coordinator(intent_obj.hass)
        queued = int(((coordinator.data or {}).get("stats") or {}).get("jobs_queued", 0)) if coordinator else 0
        response.async_set_speech(f"There are {queued} queued Pythonista jobs.")
        return response


class RunnerRefreshIntent(RunnerBaseIntent):
    """Trigger a safe manual refresh."""

    intent_type = "PythonistaRunnerRefreshIntent"
    description = "Refresh Pythonista Job Runner data"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        response = intent_obj.create_response()
        coordinator = self._coordinator(intent_obj.hass)
        if coordinator is not None:
            await coordinator.async_request_refresh()
        response.async_set_speech("Refreshed Pythonista Job Runner status.")
        return response


class RunnerPurgeDoneIntent(RunnerBaseIntent):
    """Trigger safe cleanup of completed jobs only."""

    intent_type = "PythonistaRunnerPurgeDoneIntent"
    description = "Purge completed Pythonista jobs"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        response = intent_obj.create_response()
        entries = intent_obj.hass.data.get(DOMAIN, {})
        if entries:
            data = next(iter(entries.values()))
            await intent_obj.hass.async_add_executor_job(data["client"].purge, ["done"], 0, False)
            await data["coordinator"].async_request_refresh()
        response.async_set_speech("Purged completed Pythonista jobs.")
        return response


def register_intents(hass) -> list[RunnerBaseIntent]:
    """Register runner intents and return handler instances."""
    handlers: list[RunnerBaseIntent] = [
        RunnerJobsRunningIntent(),
        RunnerQueueDepthIntent(),
        RunnerRefreshIntent(),
        RunnerPurgeDoneIntent(),
    ]
    for handler in handlers:
        intent.async_register(hass, handler)
    return handlers
