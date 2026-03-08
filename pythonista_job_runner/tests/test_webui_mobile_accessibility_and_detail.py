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
    assert 'emptyTitle.textContent = "Cannot connect"' in js
    assert 'jobsViewState === "disconnected"' in js
    assert 'tr.setAttribute("aria-selected", isSelected ? "true" : "false")' in js


def test_js_includes_keyboard_shortcut_for_search_focus() -> None:
    js = _read_js_part("40_events_init.js")

    assert 'if (ev.key !== "/") return;' in js
    assert "els.search.focus();" in js


def test_bundle_has_mobile_jobs_toolbar_help_settings_and_advanced_panels() -> None:
    html = build_webui()

    assert 'class="jobs-toolbar"' in html
    assert 'class="searchbar-row"' in html
    assert 'class="state-filters"' in html
    assert 'id="settings_modal" role="dialog"' in html
    assert 'class="modal mobile-panel"' in html
    assert 'id="about_modal" role="dialog"' in html and 'class="modal mobile-panel"' in html
    assert 'id="adv_modal" role="dialog"' in html and 'class="modal mobile-panel"' in html


def test_css_has_mobile_panel_and_filter_scroll_rules() -> None:
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "40_overlays.css").read_text(encoding="utf-8")
    layout = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert ".mobile-panel" in css
    assert "min-height:100dvh" in css
    assert "state-filters" in layout
    assert "overflow-x:auto" in layout


def test_bundle_has_sort_secondary_filters_and_no_sticky_summary_row() -> None:
    html = build_webui()

    assert 'id="job_sort"' in html
    assert 'for="job_sort">Sort<' in html
    assert 'id="filter_has_result"' in html
    assert 'id="sticky_command"' not in html
    assert "Search, filter, sort, then open details." not in html


def test_bundle_has_initial_jobs_skeleton_state() -> None:
    html = build_webui()

    assert 'class="jobs-skeleton"' in html
    assert 'class="sk sk-lg"' in html


def test_phone_layout_guardrails_for_search_clear_and_mobile_cards() -> None:
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "50_responsive.css").read_text(encoding="utf-8")

    assert ".searchbar-row{gap:6px;}" in css
    assert "#jobtable tr{border:1px solid var(--line);border-radius:12px;" in css
    assert "#jobtable td:nth-child(3)," in css


def test_help_surface_has_quick_start_samples_and_wrap_safety() -> None:
    html = build_webui()
    overlays = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "40_overlays.css").read_text(encoding="utf-8")

    assert 'summary>API reference<' in html
    assert 'summary>Quick start<' in html
    assert 'id="about_python"' in html
    assert 'data-action="copy-sample-task"' in html
    assert "#about_python,#about_curl" in overlays


def test_bundle_jobs_command_surface_is_cohesive_on_mobile() -> None:
    html = build_webui()
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'class="jobs-toolbar"' in html
    assert 'class="searchbar-row"' in html
    assert 'class="jobs-primary-row"' in html
    assert 'data-action="refresh" aria-label="Refresh jobs now"' not in html
    assert ".jobs-toolbar{" in css


def test_empty_state_copy_distinguishes_disconnected_zero_and_filtered() -> None:
    js = _read_js_part("10_render_search.js")

    assert "Use header Refresh. If it persists, open Help for troubleshooting steps." in js
    assert "Use Clear to reset search and filters quickly." in js
    assert "Run a first test task" in js


def test_single_primary_refresh_and_secondary_header_actions() -> None:
    html = build_webui()

    assert html.count('data-action="refresh"') == 1
    assert 'class="linkbtn tertiary" data-action="open-settings"' in html
    assert 'class="linkbtn tertiary" data-action="open-about"' in html
    assert 'class="linkbtn tertiary" data-action="open-advanced"' in html
