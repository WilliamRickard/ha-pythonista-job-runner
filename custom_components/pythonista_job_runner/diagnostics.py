"""Diagnostics support for Pythonista Job Runner integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_TOKEN, DOMAIN


REDACT_KEYS = {CONF_TOKEN, "authorization", "api_key", "password", "secret"}


def _redact(value: Any, key: str = "") -> Any:
    """Recursively redact secret-like values."""
    if any(secret in key.lower() for secret in REDACT_KEYS):
        return "***REDACTED***"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, key) for v in value]
    return value


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = entry_data.get("coordinator")
    client = entry_data.get("client")

    support_bundle = {}
    if client is not None:
        try:
            support_bundle = await hass.async_add_executor_job(client.support_bundle)
        except Exception as exc:  # pragma: no cover - diagnostic failure should be non-fatal
            support_bundle = {"error": str(exc)}

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": _redact(dict(entry.data or {})),
            "options": _redact(dict(entry.options or {})),
        },
        "coordinator": _redact(getattr(coordinator, "data", {}) or {}),
        "support_bundle": _redact(support_bundle),
    }


async def async_get_device_diagnostics(hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry) -> dict[str, Any]:
    """Return device-level diagnostics by enriching config diagnostics."""
    payload = await async_get_config_entry_diagnostics(hass, entry)
    payload["device"] = {
        "id": device.id,
        "name": device.name,
        "manufacturer": device.manufacturer,
        "model": device.model,
    }
    return payload
