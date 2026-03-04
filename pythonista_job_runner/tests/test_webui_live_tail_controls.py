# Version: 0.6.12-webui.1
"""Regression tests for Web UI live tail UX controls.

These tests verify that the key UX affordances (Live, Pause/Resume, Jump to
latest, Clear, and highlight chips) are present in the bundled template output.

They are intentionally lightweight and do not execute browser code.
"""

from __future__ import annotations

from pythonista_job_runner.app.webui_build import build_webui


def _bundled() -> str:
    """Return the full bundled Web UI HTML."""
    return build_webui()


def test_webui_bundle_has_live_controls() -> None:
    s = _bundled()

    assert 'id="btn_live"' in s
    assert 'id="btn_pause_resume"' in s
    assert 'id="btn_jump_latest"' in s
    assert 'id="btn_clear_log"' in s
    assert 'id="livepill"' in s


def test_webui_bundle_has_highlight_chips() -> None:
    s = _bundled()

    assert 'id="hilitebar"' in s
    assert 'id="hterm_error"' in s
    assert 'id="hterm_warn"' in s
    assert 'id="hterm_traceback"' in s
