"""Shared runtime option mutation helpers for runtime entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


def merged_option_value(entry: ConfigEntry, key: str, default):
    """Return option value with fallback to entry data and explicit default."""
    return entry.options.get(key, entry.data.get(key, default))


async def async_update_runtime_option(hass: HomeAssistant, entry: ConfigEntry, key: str, value) -> None:
    """Persist runtime option and reload entry to keep behavior predictable."""
    new_options = dict(entry.options)
    new_options[key] = value
    hass.config_entries.async_update_entry(entry, options=new_options)
    await hass.config_entries.async_reload(entry.entry_id)
