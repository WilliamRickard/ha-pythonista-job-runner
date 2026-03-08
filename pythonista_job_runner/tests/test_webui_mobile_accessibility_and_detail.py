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
    """
    Verify the search-rendering JavaScript assigns expected empty-state messages and sets ARIA selection on rows.
    
    Asserts that the JavaScript part "10_render_search.js" contains:
    - assignment of emptyTitle.textContent to "No matching jobs", "No jobs yet" and "Cannot connect";
    - a check for the disconnected view state (`jobsViewState === "disconnected"`);
    - setting of `aria-selected` on table rows via `tr.setAttribute("aria-selected", isSelected ? "true" : "false")`.
    """
    js = _read_js_part("10_render_search.js")

    assert 'emptyTitle.textContent = "No matching jobs"' in js
    assert 'emptyTitle.textContent = "No jobs yet"' in js
    assert 'emptyTitle.textContent = "Cannot connect"' in js
    assert 'jobsViewState === "disconnected"' in js
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


def test_bundle_has_sort_secondary_filters_and_sticky_command_bar() -> None:
    html = build_webui()

    assert 'id="job_sort"' in html
    assert 'id="filter_has_result"' in html
    assert 'id="sticky_command"' in html
    assert 'data-action="focus-search"' in html
    assert 'Quick jobs shortcuts' in html


def test_bundle_has_initial_jobs_skeleton_state() -> None:
    """
    Asserts the generated web UI bundle includes skeleton loading indicators for the jobs list.
    
    Checks that the HTML produced by build_webui() contains the elements used for skeleton loaders: an element with class "jobs-skeleton" and an element with classes "sk sk-lg".
    """
    html = build_webui()

    assert 'class="jobs-skeleton"' in html
    assert 'class="sk sk-lg"' in html


def test_phone_layout_guardrails_for_search_clear_and_mobile_cards() -> None:
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "50_responsive.css").read_text(encoding="utf-8")

    assert ".searchbar-row{gap:6px;}" in css
    assert "#jobtable tr{border:1px solid var(--line);border-radius:12px;" in css
    assert "#jobtable td:nth-child(3)," in css


def test_help_advanced_mobile_surface_and_wrap_safety() -> None:
    html = build_webui()
    overlays = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "40_overlays.css").read_text(encoding="utf-8")

    assert 'summary>API reference<' in html
    assert 'summary>Quick start<' in html
    assert '#about_api .api-path{overflow-wrap:anywhere;}' in overlays


def test_bundle_jobs_command_surface_is_cohesive_on_mobile() -> None:
    html = build_webui()
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'class="jobs-toolbar"' in html
    assert 'class="searchbar-row"' in html
    assert 'class="jobs-primary-row"' in html
    assert 'data-action="refresh" aria-label="Refresh jobs now"' not in html
    assert ".jobs-toolbar{" in css


def test_sticky_command_bar_is_compact_and_mobile_oriented() -> None:
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")
    responsive = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "50_responsive.css").read_text(encoding="utf-8")
    events = _read_js_part("40_events_init.js")

    assert ".sticky-command{" in css
    assert "flex-wrap:nowrap;" in css
    assert ".sticky-command .muted" in css
    assert "isNarrow() && r.bottom < 0" in events
    assert ".sticky-command{top:6px;gap:6px;padding:4px 7px;}" in responsive


def test_empty_state_copy_distinguishes_disconnected_zero_and_filtered() -> None:
    js = _read_js_part("10_render_search.js")

    assert "Use header Refresh. If it persists, open Help for troubleshooting steps." in js
    assert "Use Clear to reset search and filters quickly." in js
    assert "Runner is connected but idle." in js


def test_single_primary_refresh_and_quiet_secondary_header_actions() -> None:
    html = build_webui()

    assert html.count('data-action="refresh"') == 1
    assert 'class="linkbtn tertiary" data-action="open-about"' in html
    assert 'class="linkbtn tertiary" data-action="open-advanced"' in html


def test_passive_metadata_rendered_as_non_interactive_visuals() -> None:
    js = _read_js_part("10_render_search.js")

    assert 'span.className = "pill passive-pill";' in js
