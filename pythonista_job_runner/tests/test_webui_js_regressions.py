"""Regression tests for key Web UI JavaScript safety fixes.

These tests deliberately check for small, behaviour-critical patterns in the JS
sources to reduce the chance of reintroducing subtle UI bugs.
"""

from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_tail_offsets_accept_zero() -> None:
    """Offsets should not treat 0 as missing (avoid `||` fallback)."""

    p = Path(__file__).resolve().parent.parent / "app" / "webui_js" / "30_refresh_actions.js"
    s = _read(p)

    assert "stdout_next ?? offsets.stdout" in s
    assert "stderr_next ?? offsets.stderr" in s


def test_parse_endpoint_path_rejects_protocol_relative() -> None:
    """Protocol-relative paths (`//host/...`) must be rejected."""

    p = Path(__file__).resolve().parent.parent / "app" / "webui_js" / "10_render_search.js"
    s = _read(p)

    assert "!parts[1].startsWith(\"//\")" in s
    assert "!s.startsWith(\"//\")" in s


def test_jump_error_prefers_rendered_text() -> None:
    """Jump-to-error should align indices with the rendered log text."""

    p = Path(__file__).resolve().parent.parent / "app" / "webui_js" / "10_render_search.js"
    s = _read(p)

    assert "const visibleTxt" in s
    assert "els.logview.textContent" in s


def test_render_log_uses_escaped_newline_literals() -> None:
    """Rendered log splitting and joining must keep escaped newline literals."""

    part = Path(__file__).resolve().parent.parent / "app" / "webui_js" / "10_render_search.js"
    s = _read(part)

    assert 'slice.split("\\n")' in s
    assert 'out.join("\\n")' in s

    built = _read(Path(__file__).resolve().parent.parent / "app" / "webui.js")
    assert 'slice.split("\\n")' in built
    assert 'out.join("\\n")' in built


def test_jobs_refresh_uses_silent_mode_and_in_place_rows() -> None:
    """Routine polling should be silent and avoid full tbody rebuilds."""

    refresh = _read(Path(__file__).resolve().parent.parent / "app" / "webui_js" / "30_refresh_actions.js")
    render = _read(Path(__file__).resolve().parent.parent / "app" / "webui_js" / "10_render_search.js")

    assert "await refreshAll({ silent: true });" in refresh
    assert "if (els.jobs_loading && !silent)" in render
    assert "function _patchRow(tr, j)" in render
    assert 'tbody.textContent = ""' not in render


def test_jobs_filters_include_sort_and_secondary_flags() -> None:
    render = _read(Path(__file__).resolve().parent.parent / "app" / "webui_js" / "10_render_search.js")

    assert 'sortMode === "oldest"' in render
    assert 'sortMode === "active"' in render
    assert 'filterHasResult' in render


def test_sticky_command_bar_state_sync_present() -> None:
    core = _read(Path(__file__).resolve().parent.parent / "app" / "webui_js" / "00_core.js")
    events = _read(Path(__file__).resolve().parent.parent / "app" / "webui_js" / "40_events_init.js")

    assert "function updateStickySummary()" in core
    assert "sticky_summary" in core
    assert "syncSticky" in events


def test_row_overflow_actions_used_instead_of_many_inline_buttons() -> None:
    render = _read(Path(__file__).resolve().parent.parent / "app" / "webui_js" / "10_render_search.js")

    assert 'row-overflow' in render
    assert 'Copy id' in render


def test_sticky_command_focus_action_targets_search() -> None:
    events = _read(Path(__file__).resolve().parent.parent / "app" / "webui_js" / "40_events_init.js")

    assert 'action === "focus-search"' in events
    assert 'els.search.focus();' in events


def test_jobs_command_row_keeps_refresh_in_primary_surface() -> None:
    html = _read(Path(__file__).resolve().parent.parent / "app" / "webui_html" / "20_jobs.html")

    assert 'class="searchbar-row command-row"' in html
    assert 'data-action="refresh" aria-label="Refresh jobs now"' in html


def test_localstorage_access_uses_safe_wrappers() -> None:
    core = _read(Path(__file__).resolve().parent.parent / "app" / "webui_js" / "00_core.js")
    init = _read(Path(__file__).resolve().parent.parent / "app" / "webui_js" / "40_events_init.js")

    assert "function storageGet(" in core
    assert "function storageSet(" in core
    assert "function storageRemove(" in core

    assert "localStorage.getItem(" not in core
    assert "localStorage.setItem(" not in core
    assert "localStorage.removeItem(" not in core

    assert "localStorage.getItem(" not in init
    assert "localStorage.setItem(" not in init
    assert "localStorage.removeItem(" not in init
    assert "storageGet(" in init
    assert "storageSet(" in init
