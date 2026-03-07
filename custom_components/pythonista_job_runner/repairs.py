"""Repairs issue helpers for Pythonista Job Runner integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, ISSUE_AUTH, ISSUE_UNREACHABLE


def create_unreachable_issue(hass: HomeAssistant, entry_id: str, detail: str) -> None:
    """Create/update unreachable endpoint repair issue for an entry."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_UNREACHABLE}_{entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_UNREACHABLE,
        translation_placeholders={"detail": detail},
    )


def create_auth_issue(hass: HomeAssistant, entry_id: str, detail: str) -> None:
    """Create/update auth failure repair issue for an entry."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_AUTH}_{entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_AUTH,
        translation_placeholders={"detail": detail},
    )


def clear_issues(hass: HomeAssistant, entry_id: str) -> None:
    """Clear known issues for an entry."""
    for issue in (ISSUE_UNREACHABLE, ISSUE_AUTH):
        ir.async_delete_issue(hass, DOMAIN, f"{issue}_{entry_id}")
