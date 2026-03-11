# Version: 0.6.17-webui.1
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
    assert 'id="detail_inline_state"' in html
    assert 'id="detail_timeline" class="timeline"' in html
    assert 'id="detail_result_summary"' in html
    assert 'id="detail_limits_summary"' in html
    assert 'id="detail_failure_summary"' in html
    assert 'detail-more-actions' in html
    assert 'id="detail_breadcrumb_current"' in html
    assert 'detail-meta-block' in html
    assert 'detail-log-shell' in html


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
    assert "height:92dvh" in css
    assert "overflow-y:auto" in css
    assert "-webkit-overflow-scrolling:touch" in css
    assert "touch-action:pan-y" in css
    assert "state-filters" in layout
    assert "overflow-x:auto" in layout


def test_bundle_has_sort_secondary_filters_and_no_sticky_summary_row() -> None:
    html = build_webui()

    assert 'id="sort_menu"' in html
    assert 'id="sort_summary"' in html
    assert 'id="filter_has_result"' in html
    assert 'id="sticky_command"' not in html
    assert "Search, filter, sort, then open details." not in html


def test_bundle_has_initial_jobs_skeleton_state() -> None:
    html = build_webui()

    assert 'class="jobs-skeleton"' in html
    assert 'class="sk sk-lg"' in html


def test_bundle_has_collapsible_queue_summary_and_single_primary_empty_action() -> None:
    html = build_webui()

    assert 'id="queue_details"' in html
    assert 'id="queue_summary_text"' in html
    assert html.count('data-action="copy-sample-task"') == 2
    assert 'Open quick start' in html


def test_phone_layout_guardrails_for_search_clear_and_mobile_cards() -> None:
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "50_responsive.css").read_text(encoding="utf-8")

    assert ".searchbar-row{gap:6px;}" in css
    assert "#jobtable tr{border:1px solid color-mix(in srgb, var(--line) 62%, transparent);border-radius:14px;" in css
    assert "#jobtable td:nth-child(2)," in css


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
    assert "Copy the sample task, run it from Pythonista" in js


def test_single_primary_refresh_and_secondary_header_actions() -> None:
    html = build_webui()

    assert html.count('data-action="refresh"') == 1
    assert 'id="header_more_toggle"' in html
    assert 'id="header_more_panel"' in html
    assert 'data-action="open-settings"' in html
    assert 'data-action="open-about"' in html
    assert 'data-action="open-advanced"' in html
    assert 'System details' in html
    assert 'id="settings_direction"' in html


def test_bundle_has_command_and_confirm_overlays() -> None:
    html = build_webui()

    assert 'id="command_modal" role="dialog"' in html
    assert 'id="row_menu" class="floating-menu"' in html
    assert 'id="command_input" type="search"' in html
    assert 'id="confirm_modal" role="alertdialog"' in html
    assert 'data-action="confirm-accept"' in html


def test_js_uses_custom_confirm_overlay_and_command_shortcut() -> None:
    events = _read_js_part("40_events_init.js")
    render = _read_js_part("10_render_search.js")
    refresh = _read_js_part("30_refresh_actions.js")

    assert 'openConfirm({' in render
    assert 'openConfirm({' in refresh
    assert 'window.confirm(' not in render
    assert 'window.confirm(' not in refresh
    assert 'openCommand();' in events
    assert 'String(ev.key).toLowerCase() === "k"' in events


def test_detail_panel_prioritises_summary_before_logs() -> None:
    html = build_webui()
    core = _read_js_part("00_core.js")

    assert 'class="detail-priority-strip"' in html
    assert 'data-tab="overview" id="tab_overview"' in html
    assert html.index('id="tab_overview"') < html.index('id="tab_stdout"')
    assert 'let currentTab = "overview";' in core
    assert '<summary>Log controls</summary>' in html


def test_bundle_has_row_popover_progress_and_scroll_areas() -> None:
    html = build_webui()
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'id="row_popover" class="floating-popover"' in html
    assert 'id="row_popover_progress" class="progress popover-progress"' in html
    assert 'id="detail_progress" class="progress detail-progress"' in html
    assert 'class="scroll-area scroll-area-log"' in html
    assert 'class="scroll-area scroll-area-meta"' in html
    assert '.scroll-area{' in css
    assert '.tooltip-target' in css


def test_bundle_has_combobox_calendar_pagination_and_splitter() -> None:
    html = build_webui()
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "50_responsive.css").read_text(encoding="utf-8")

    assert 'id="filter_user"' in html
    assert 'id="filter_user_list"' in html
    assert 'id="filter_since" type="date"' in html
    assert 'id="jobs_pagination" class="pagination-shell"' in html
    assert 'id="desktop_splitter" class="desktop-splitter"' in html
    assert '--jobs-pane-width' in css


def test_bundle_hover_preview_and_pagination_helpers_exist() -> None:
    js = _read_js_part("10_render_search.js")

    assert 'updateUserFilterOptions(' in js
    assert 'updatePaginationUi(' in js
    assert 'setDatePreset(' in js
    assert 'goToNextPage(' in js
    assert 'rowPopoverMode = mode || "manual"' in js
    assert 'Preview ${jobId}' in js


def test_header_more_panel_is_hidden_by_default_in_mobile_bundle() -> None:
    """Mobile bundle should keep the More panel hidden until activated."""

    html = build_webui()
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'id="header_more_panel" class="header-more-panel" role="menu" aria-label="Secondary actions" hidden' in html
    assert '.header-more-panel[hidden]{display:none !important;}' in css


def test_bundle_header_more_toggle_uses_button_and_panel_contract() -> None:
    """The header More menu should remain a button-plus-panel contract."""

    html = build_webui()
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'id="header_more_toggle"' in html
    assert 'data-action="toggle-header-more"' in html
    assert 'id="header_more_panel"' in html
    assert 'class="header-more-panel"' in html
    assert '<details class="header-more-menu"' not in html
    assert '.header-more-panel[hidden]{display:none !important;}' in css
