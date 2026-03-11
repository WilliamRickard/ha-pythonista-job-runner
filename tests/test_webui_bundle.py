# Version: 0.6.12-webui.7
"""Tests that generated Web UI outputs match the bundled sources."""

from __future__ import annotations

from webui_build import check_webui


def test_webui_html_is_up_to_date() -> None:
    """Fail if webui.html or webui.css have not been regenerated from sources."""
    check_webui()
