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
    assert 'emptyTitle.textContent = "No jobs received yet"' in js
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
    assert 'Queue overview' in html
    assert 'id="queue_summary_text"' in html
    assert html.count('data-action="copy-sample-task"') == 2
    assert 'Open quick start' in html


def test_header_and_jobs_surfaces_expose_supportive_microcopy_and_clear_primary_action() -> None:
    html = build_webui()

    assert 'class="brand-support"' in html
    assert 'Monitor job health and take action quickly.' in html
    assert 'class="jobs-support"' in html
    assert 'aria-label="Refresh queue and jobs"' in html


def test_css_has_reduced_motion_guardrail_and_modern_toolbar_density() -> None:
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert "prefers-reduced-motion: reduce" in css
    assert ".jobs-toolbar{display:flex;flex-direction:column;gap:8px;" in css
    assert ".input-group{display:flex;align-items:center;gap:0;" in css


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

    assert "Use Refresh jobs first. If still disconnected, open Help and run health checks." in js
    assert "Use Clear to reset filters, then start with Running or Errors." in js
    assert "Copy the sample task, run it in Pythonista" in js


def test_single_primary_refresh_and_secondary_header_actions() -> None:
    html = build_webui()

    assert html.count('data-action="refresh"') == 2
    assert 'data-action="refresh" data-action-role="global-primary"' in html
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


def test_mobile_header_and_jobs_surface_are_compact_first() -> None:
    html = build_webui()
    responsive = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "50_responsive.css").read_text(encoding="utf-8")

    assert 'class="brand brand-compact"' in html
    assert 'class="jobs-heading"' in html
    assert '.brand-compact .brand-support{display:none;}' in responsive
    assert '.jobs-support{display:none;}' in responsive


def test_bundle_has_guided_setup_sequence_and_collapsed_advanced_groups() -> None:
    html = build_webui()

    assert 'class="modal-body setup-guided"' in html
    assert 'Recommended path:' in html
    assert 'Step 1 · Persistent packages' in html
    assert 'Step 2 · Setup target' in html
    assert 'Advanced · Wheel uploads' in html


def test_bundle_has_grouped_log_controls_for_mobile_scanability() -> None:
    html = build_webui()
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'class="logtools log-controls-group" id="logtools"' in html
    assert 'aria-label="Live session controls"' in html
    assert 'aria-label="Readability controls"' in html
    assert 'id="hilitebar" aria-label="Highlight terms"' in html
    assert 'id="findbar" aria-label="Find in log controls"' in html
    assert '.log-controls-group{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;}' in css


def test_filters_summary_and_mobile_compaction_rules_exist() -> None:
    html = build_webui()
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "50_responsive.css").read_text(encoding="utf-8")

    assert 'id="filters_summary">Refine list<' in html
    assert 'Result zip only' in html
    assert '.toggle-group .toggle-item{min-height:36px;padding:7px 10px;font-size:12px;}' in css
    assert '.filters-field-group{gap:8px;}' in css


def test_bundle_microcopy_is_action_oriented_for_jobs_and_setup() -> None:
    html = build_webui()

    assert 'Check state chips first, then use filters only when you need to narrow the queue.' in html
    assert 'No jobs received yet' in html
    assert 'open the newest job first' in html
    assert 'Home Assistant add-on package setup' in html


def test_advanced_modal_uses_progressive_disclosure_defaults() -> None:
    html = build_webui()

    assert 'class="modal-body adv-guided"' in html
    assert '<summary>Package setup</summary>' in html
    assert '<summary>Package storage</summary>' in html
    assert '<summary>Package profiles</summary>' in html
    assert '<details open>\n          <summary>Package setup</summary>' not in html


def test_js_strengthens_status_semantics_and_operator_first_row_copy() -> None:
    js = _read_js_part("00_core.js") + _read_js_part("10_render_search.js") + _read_js_part("20_detail_meta.js")

    assert 'labelByState' in js
    assert 'detailByState' in js
    assert 'aria-label", `${label.textContent}, ${detailByState[cls] || "state"}`' in js
    assert 'jobbtn-title' in js
    assert 'jobbtn-id' in js
    assert 'Press Enter for details.' in js


def test_css_has_shape_semantics_and_ha_context_cues() -> None:
    css_jobs = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "20_jobs_table.css").read_text(encoding="utf-8")
    css_layout = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert '.badge[data-state="queued"]{border-style:dashed;}' in css_jobs
    assert '.badge[data-state="error"] .badge-icon' in css_jobs
    assert '.jobbtn-title{' in css_jobs
    assert '.jobbtn-id{' in css_jobs
    assert 'jobs-support::before{content:"Home Assistant add-on · "' in css_layout


def test_bundle_has_systematic_action_roles_and_segmented_detail_shell() -> None:
    html = build_webui()
    layout = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'data-action-role="global-primary"' in html
    assert 'data-action-role="global-overflow"' in html
    assert 'data-action-role="section-primary"' in html
    assert 'data-action-role="section-destructive"' in html
    assert 'data-action-role="section-overflow"' in html
    assert 'class="detail-segmented-shell"' in html
    assert '.detail-segmented-shell{' in layout


def test_bundle_distinguishes_routine_and_advanced_detail_sections() -> None:
    html = build_webui()
    layout = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'Routine checks' in html
    assert 'Advanced diagnostics' in html
    assert 'data-section="advanced"' in html
    assert '.section-kicker{' in layout
    assert '.section-kicker-advanced{' in layout


def test_empty_states_have_retry_control_and_stateful_icon_behaviour() -> None:
    html = build_webui()
    js = _read_js_part("10_render_search.js")
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "20_jobs_table.css").read_text(encoding="utf-8")

    assert 'id="empty_retry"' in html
    assert 'if (emptyRetry) emptyRetry.hidden = jobsViewState !== "disconnected";' in js
    assert 'if (emptyIcon) {' in js
    assert 'emptyShell.dataset.state = mode;' in js
    assert '.empty[data-state="disconnected"] .empty-icon' in css


def test_jobs_surface_has_triage_strip_and_urgent_filter_actions() -> None:
    html = build_webui()
    js = _read_js_part("10_render_search.js")
    css = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "20_jobs_table.css").read_text(encoding="utf-8")

    assert 'id="jobs_triage" class="triage-strip"' in html
    assert 'id="triage_errors" data-action="set-view" data-view="error"' in html
    assert 'id="triage_running" data-action="set-view" data-view="running"' in html
    assert 'id="triage_queued" data-action="set-view" data-view="queued"' in html
    assert 'const staleQueuedCount = jobsCache.filter((j) => _timingSignals(j).staleQueued).length;' in js
    assert 'triageShell.dataset.urgency = urgentCount > 0 ? "urgent" : "clear";' in js
    assert '.triage-strip[data-urgency="urgent"]' in css


def test_row_model_prioritises_actor_state_time_and_row_action_roles() -> None:
    js = _read_js_part("10_render_search.js")
    css_layout = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'function _timingSignals(job)' in js
    assert 'titleEl.textContent = `${actor} · ${model.label}`;' in js
    assert 'idEl.textContent = jobId ? `${age || "now"} old · ${dur || "not started"} · ID ${jobId}` : "";' in js
    assert 'tr.children[3].textContent = timing.longRunning ? `${dur} · long` : dur;' in js
    assert 'btnView.setAttribute("data-action-role", "row-primary");' in js
    assert 'overflow.setAttribute("data-action-role", "row-overflow");' in js
    assert '[data-action-role="row-primary"]' in css_layout


def test_detail_defaults_to_collapsed_advanced_shell_with_context_chips() -> None:
    html = build_webui()
    detail_js = _read_js_part("20_detail_meta.js")
    layout = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'class="detail-advanced-shell" data-section="advanced"' in html
    assert '<summary><span class="section-kicker section-kicker-advanced">Advanced diagnostics</span></summary>' in html
    assert 'id="detail_context_actor"' in html
    assert 'id="detail_context_age"' in html
    assert 'id="detail_context_duration"' in html
    assert 'if (els.detail_context_scope) els.detail_context_scope.textContent = "Scope: Jobs → Detail";' in detail_js
    assert 'function _detailTimingSignals(st)' in detail_js
    assert '.detail-advanced-shell{' in layout
    assert '.context-chip{' in layout


def test_success_states_use_resolved_language_in_rows_and_detail() -> None:
    js_rows = _read_js_part("10_render_search.js")
    js_detail = _read_js_part("20_detail_meta.js")

    assert 'lead: resultReady ? "Resolved · archive ready" : "Resolved"' in js_rows
    assert 'done: "Completed and resolved"' in js_detail
    assert 'Resolved successfully.' in js_detail
    assert 'Job resolved successfully with no failure detected.' in js_detail


def test_risk_levels_are_explicit_for_global_detail_and_maintenance_actions() -> None:
    html = build_webui()
    layout = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")
    overlays = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "40_overlays.css").read_text(encoding="utf-8")

    assert 'data-risk-level="state-change"' in html
    assert 'data-risk-level="destructive"' in html
    assert 'data-risk-level="harmless"' in html
    assert '[data-risk-level="state-change"]' in layout
    assert '[data-risk-level="destructive"]' in layout
    assert '.modal [data-risk-level="destructive"]' in overlays


def test_context_cues_include_mode_pill_and_detail_orientation_labels() -> None:
    html = build_webui()
    core_js = _read_js_part("00_core.js")
    detail_js = _read_js_part("20_detail_meta.js")

    assert 'id="ui_mode_pill"' in html
    assert 'id="ui_mode_label"' in html
    assert 'function updateModeContextUi()' in core_js
    assert 'label.textContent = `Mode: ${paneLabel} · ${tabLabel}`;' in core_js
    assert 'if (els.detail_context_scope) els.detail_context_scope.textContent = "Scope: Jobs → Detail";' in detail_js


def test_density_mode_is_surface_specific_for_list_form_and_reading_areas() -> None:
    layout = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'body[data-density="comfortable"]{--list-row-pad:12px;--form-pad:12px;--read-line:1.5;}' in layout
    assert 'body[data-density="compact"]{--list-row-pad:8px;--form-pad:9px;--read-line:1.38;}' in layout
    assert '.tablewrap th,.tablewrap td{padding:var(--list-row-pad,12px);}' in layout
    assert '.modal-body .field-shell{padding:var(--form-pad,12px);}' in layout
    assert '.scroll-area-log pre,.scroll-area-control{line-height:var(--read-line,1.5);}' in layout


def test_inline_help_is_progressively_disclosed_in_setup_help_and_detail() -> None:
    html = build_webui()
    layout = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'Need help with Step 1?' in html
    assert 'Need help with Step 3?' in html
    assert 'Why these steps work' in html
    assert 'Need deeper troubleshooting guidance?' in html
    assert '.inline-help{' in layout
    assert '.detail-inline-help{' in layout


def test_primary_path_controls_are_explicit_on_jobs_detail_and_setup() -> None:
    html = build_webui()
    layout = (Path(__file__).resolve().parent.parent / "app" / "webui_css" / "10_layout.css").read_text(encoding="utf-8")

    assert 'id="jobs_primary_path" class="primary-path-strip"' in html
    assert 'id="jobs_primary_open" data-action="open-primary-job"' in html
    assert 'class="detail-primary-path"' in html
    assert 'class="setup-primary-path"' in html
    assert '.primary-path-strip{' in layout
    assert '.detail-primary-path{' in layout
    assert '.setup-primary-path{' in layout


def test_primary_path_action_selects_priority_job_from_current_cache() -> None:
    js = _read_js_part("10_render_search.js") + _read_js_part("40_events_init.js")

    assert 'function openPrimaryJob() {' in js
    assert 'setView(String(priority.state || "all"));' in js
    assert 'selectJob(String(priority.job_id || ""));' in js
    assert 'if (action === "open-primary-job") openPrimaryJob();' in js


def test_detail_handoff_panel_preserves_overview_to_detail_context() -> None:
    html = build_webui()
    js = _read_js_part("20_detail_meta.js") + _read_js_part("40_events_init.js")

    assert 'id="detail_handoff" class="detail-handoff"' in html
    assert 'id="detail_handoff_title"' in html
    assert 'id="detail_handoff_body"' in html
    assert 'if (els.detail_handoff) els.detail_handoff.hidden = false;' in js
    assert 'els.detail_handoff_title.textContent = "Opened from Jobs";' in js
    assert 'els.detail_handoff_body.textContent = `${actor} · ${stateText} · ${age} old`;' in js
    assert 'els.detail_handoff = document.getElementById("detail_handoff");' in js
