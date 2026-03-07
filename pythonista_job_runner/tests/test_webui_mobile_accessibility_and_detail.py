"""Regression tests for mobile UX, accessibility, and detail-lifecycle Web UI improvements."""

from __future__ import annotations

from pathlib import Path

from webui_build import build_webui


def _read_js_part(name: str) -> str:
    base = Path(__file__).resolve().parent.parent / "app" / "webui_js"
    return (base / name).read_text(encoding="utf-8")


def test_bundle_has_skip_link_and_accessible_jobs_states() -> None:
    html = build_webui()

    assert 'class="skip-link" href="#main_content"' in html
    assert 'id="main_content" tabindex="-1"' in html
    assert 'id="jobs_loading" class="loading" role="status" aria-live="polite"' in html
    assert 'id="jobs_banner" class="banner" role="status" aria-live="polite"' in html
    assert 'id="empty_title"' in html
    assert 'id="empty_body"' in html


def test_bundle_has_detail_lifecycle_sections() -> None:
    html = build_webui()

    assert 'id="detail_state_banner"' in html
    assert 'id="detail_timeline" class="timeline"' in html
    assert 'id="detail_result_summary"' in html
    assert 'id="detail_limits_summary"' in html
    assert 'id="detail_failure_summary"' in html


def test_js_tracks_empty_state_messages_and_row_selection() -> None:
    js = _read_js_part("10_render_search.js")

    assert 'emptyTitle.textContent = "No matching jobs"' in js
    assert 'emptyTitle.textContent = "No jobs yet"' in js
    assert 'tr.setAttribute("aria-selected", isSelected ? "true" : "false")' in js


def test_js_renders_state_banner_timeline_and_insights() -> None:
    js = _read_js_part("20_detail_meta.js")

    assert "function _setStateBanner(st)" in js
    assert "function _renderTimeline(st)" in js
    assert "function _renderInsights(st)" in js
    assert "els.detail_state_banner.classList.add(state)" in js


def test_js_includes_keyboard_shortcut_for_search_focus() -> None:
    js = _read_js_part("40_events_init.js")

    assert 'if (ev.key !== "/") return;' in js
    assert "els.search.focus();" in js
