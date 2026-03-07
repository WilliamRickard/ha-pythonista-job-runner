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


def test_bundle_has_mobile_jobs_toolbar_and_panels() -> None:
    html = build_webui()

    assert 'class="jobs-toolbar"' in html
    assert 'class="searchbar-row"' in html
    assert 'class="state-filters"' in html
    assert 'id="about_modal" role="dialog"' in html and 'class="modal mobile-panel"' in html
    assert 'id="adv_modal" role="dialog"' in html and 'class="modal mobile-panel"' in html


def test_css_has_mobile_panel_and_filter_scroll_rules() -> None:
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "40_overlays.css").read_text(encoding="utf-8")
    layout = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert ".mobile-panel" in css
    assert "min-height:100dvh" in css
    assert "state-filters" in layout
    assert "overflow-x:auto" in layout
