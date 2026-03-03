"""Regression tests for Web UI live tail UX controls.

These tests verify that the key UX affordances (Live, Pause/Resume, Jump to
latest, Clear, and highlight chips) are present in the source templates.

They are intentionally lightweight and do not execute browser code.
"""

from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_webui_src_has_live_controls() -> None:
    p = Path(__file__).resolve().parent.parent / "app" / "webui_src.html"
    s = _read(p)

    assert 'id="btn_live"' in s
    assert 'id="btn_pause_resume"' in s
    assert 'id="btn_jump_latest"' in s
    assert 'id="btn_clear_log"' in s
    assert 'id="livepill"' in s


def test_webui_src_has_highlight_chips() -> None:
    p = Path(__file__).resolve().parent.parent / "app" / "webui_src.html"
    s = _read(p)

    assert 'id="hilitebar"' in s
    assert 'data-action="toggle-hterm"' in s
    assert 'id="hterm_input"' in s


def test_webui_js_has_auto_pause_scroll() -> None:
    p = Path(__file__).resolve().parent.parent / "app" / "webui_js" / "00_core.js"
    s = _read(p)

    assert "function onLogScrollAutoPause" in s
    assert "programmaticScrollAt" in s
