# Version: 0.3.0-services.1
"""Service registration for Pythonista Job Runner integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    DOMAIN,
    SERVICE_BUILD_PACKAGE_PROFILE,
    SERVICE_CANCEL_JOB,
    SERVICE_PRUNE_PACKAGE_CACHE,
    SERVICE_PURGE_DONE_JOBS,
    SERVICE_PURGE_FAILED_JOBS,
    SERVICE_PURGE_JOBS,
    SERVICE_PURGE_PACKAGE_CACHE,
    SERVICE_REFRESH,
)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    async def _purge(call: ServiceCall) -> None:
        entry_id = call.data["entry_id"]
        states = call.data.get("states", [])
        older_than_hours = int(call.data.get("older_than_hours", 0))
        dry_run = bool(call.data.get("dry_run", False))
        entry_data = hass.data[DOMAIN][entry_id]
        await hass.async_add_executor_job(entry_data["client"].purge, states, older_than_hours, dry_run)
        await entry_data["coordinator"].async_request_refresh()

    async def _purge_predefined(call: ServiceCall, states: list[str]) -> None:
        entry_id = call.data["entry_id"]
        older_than_hours = int(call.data.get("older_than_hours", 0))
        dry_run = bool(call.data.get("dry_run", False))
        entry_data = hass.data[DOMAIN][entry_id]
        await hass.async_add_executor_job(entry_data["client"].purge, states, older_than_hours, dry_run)
        await entry_data["coordinator"].async_request_refresh()

    async def _refresh(call: ServiceCall) -> None:
        entry_data = hass.data[DOMAIN][call.data["entry_id"]]
        await entry_data["coordinator"].async_request_refresh()

    async def _cancel(call: ServiceCall) -> None:
        entry_data = hass.data[DOMAIN][call.data["entry_id"]]
        await hass.async_add_executor_job(entry_data["client"].cancel, call.data["job_id"])
        await entry_data["coordinator"].async_request_refresh()

    async def _build_package_profile(call: ServiceCall) -> None:
        entry_data = hass.data[DOMAIN][call.data["entry_id"]]
        profile_name = str(call.data.get("profile_name", "") or "")
        rebuild = bool(call.data.get("rebuild", False))
        await hass.async_add_executor_job(entry_data["client"].build_package_profile, profile_name, rebuild)
        await entry_data["coordinator"].async_request_refresh()

    async def _prune_package_cache(call: ServiceCall) -> None:
        entry_data = hass.data[DOMAIN][call.data["entry_id"]]
        reason = str(call.data.get("reason", "manual") or "manual")
        await hass.async_add_executor_job(entry_data["client"].prune_package_cache, reason)
        await entry_data["coordinator"].async_request_refresh()

    async def _purge_package_cache(call: ServiceCall) -> None:
        entry_data = hass.data[DOMAIN][call.data["entry_id"]]
        reason = str(call.data.get("reason", "manual") or "manual")
        include_venvs = bool(call.data.get("include_venvs", False))
        include_imported_wheels = bool(call.data.get("include_imported_wheels", False))
        await hass.async_add_executor_job(
            entry_data["client"].purge_package_cache,
            reason,
            include_venvs,
            include_imported_wheels,
        )
        await entry_data["coordinator"].async_request_refresh()

    common_schema = vol.Schema(
        {
            vol.Required("entry_id"): str,
            vol.Optional("older_than_hours", default=0): int,
            vol.Optional("dry_run", default=False): bool,
        }
    )

    if not hass.services.has_service(DOMAIN, SERVICE_PURGE_JOBS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_PURGE_JOBS,
            _purge,
            schema=vol.Schema(
                {
                    vol.Required("entry_id"): str,
                    vol.Optional("states", default=[]): [str],
                    vol.Optional("older_than_hours", default=0): int,
                    vol.Optional("dry_run", default=False): bool,
                }
            ),
        )

    async def _purge_done(call: ServiceCall) -> None:
        await _purge_predefined(call, ["done"])

    async def _purge_failed(call: ServiceCall) -> None:
        await _purge_predefined(call, ["error"])

    if not hass.services.has_service(DOMAIN, SERVICE_PURGE_DONE_JOBS):
        hass.services.async_register(DOMAIN, SERVICE_PURGE_DONE_JOBS, _purge_done, schema=common_schema)
    if not hass.services.has_service(DOMAIN, SERVICE_PURGE_FAILED_JOBS):
        hass.services.async_register(DOMAIN, SERVICE_PURGE_FAILED_JOBS, _purge_failed, schema=common_schema)
    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        hass.services.async_register(DOMAIN, SERVICE_REFRESH, _refresh, schema=vol.Schema({vol.Required("entry_id"): str}))
    if not hass.services.has_service(DOMAIN, SERVICE_CANCEL_JOB):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CANCEL_JOB,
            _cancel,
            schema=vol.Schema({vol.Required("entry_id"): str, vol.Required("job_id"): str}),
        )
    if not hass.services.has_service(DOMAIN, SERVICE_BUILD_PACKAGE_PROFILE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_BUILD_PACKAGE_PROFILE,
            _build_package_profile,
            schema=vol.Schema(
                {
                    vol.Required("entry_id"): str,
                    vol.Optional("profile_name", default=""): str,
                    vol.Optional("rebuild", default=False): bool,
                }
            ),
        )
    if not hass.services.has_service(DOMAIN, SERVICE_PRUNE_PACKAGE_CACHE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_PRUNE_PACKAGE_CACHE,
            _prune_package_cache,
            schema=vol.Schema({vol.Required("entry_id"): str, vol.Optional("reason", default="manual"): str}),
        )
    if not hass.services.has_service(DOMAIN, SERVICE_PURGE_PACKAGE_CACHE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_PURGE_PACKAGE_CACHE,
            _purge_package_cache,
            schema=vol.Schema(
                {
                    vol.Required("entry_id"): str,
                    vol.Optional("reason", default="manual"): str,
                    vol.Optional("include_venvs", default=False): bool,
                    vol.Optional("include_imported_wheels", default=False): bool,
                }
            ),
        )
