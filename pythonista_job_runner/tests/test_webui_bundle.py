"""Tests that webui.html matches the bundled sources."""
from __future__ import annotations

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from webui_build import check_webui  # noqa: E402


def test_webui_html_is_up_to_date() -> None:
    """Fail if webui.html has not been regenerated from sources."""
    check_webui()
