"""Tests that webui.html matches the bundled sources."""

from __future__ import annotations

from webui_build import check_webui


def test_webui_html_is_up_to_date() -> None:
    """Fail if webui.html has not been regenerated from sources."""
    check_webui()
