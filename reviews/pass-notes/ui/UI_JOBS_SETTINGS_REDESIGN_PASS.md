# UI Jobs + Settings Redesign Pass (Living Plan)

## Current Jobs-flow problems

1. Jobs subtitle text is redundant clutter.
2. Sticky summary strip duplicates context and adds cognitive noise.
3. `Newest` appears without clear sort affordance.
4. Too many stacked control layers before job content.
5. Empty/help path is abstract for first run and lacks copyable working sample.
6. Runtime/UI settings are scattered (header metadata + Advanced) instead of a dedicated Settings surface.
7. Queue snapshot has too much visual weight relative to Jobs.
8. Screen reads as compressed dashboard, not a calm mobile operations workflow.

## Controls/text to remove

- Remove Jobs subtitle hint text.
- Remove sticky command summary row from Jobs surface.
- Remove passive header auto-refresh metadata line (keep only system facts there).
- Remove runtime/UI controls from Advanced modal.
- Remove ambiguous bare `Newest` semantics in favor of explicit `Sort` label.

## New Jobs information architecture

- Jobs header row: `Jobs` + compact count.
- Toolbar row: Search + conditional Clear + `Sort` label/select.
- Primary filters row: All / Running / Queued / Errors / Done.
- Secondary filters collapsed under one lightweight `Filters` details control.
- Immediate content area: job list or empty state with actionable next steps.

## Settings ownership decisions

### Belongs in Web UI Settings
- Auto refresh toggle (UI behavior).
- Poll interval (UI behavior).
- Default sort (UI preference).
- UI density (UI-only presentation preference).
- Secondary filter preference persistence (`Only show result zip`).

### Must remain outside Web UI Settings
- Supervisor-managed add-on install/configuration.
- Integration-owned options not safe at runtime in web UI.
- Backend retention controls unless existing runtime-safe API exists (no new unsafe mutation added).

## Ordered milestones

1. Remove redundant rows/text, simplify header secondary actions, quiet metadata, rebalance hierarchy.
2. Rebuild Jobs list-first controls, explicit Sort, unified search/clear/filter system, preserve no-flicker polling behavior.
3. Improve empty state, add copyable sample Python task, rewrite Help quick start with concrete success path and auth guidance.
4. Add dedicated Settings surface; move runtime/UI controls there; simplify Advanced to maintenance-only actions.
5. Shrink queue snapshot, tighten hierarchy/accessibility/spacing, provide viewport evidence (320/375/430 + wide), final truthfulness sweep.

## Files expected to change

- `UI_JOBS_SETTINGS_REDESIGN_PASS.md`
- `pythonista_job_runner/app/webui_html/00_shell.html`
- `pythonista_job_runner/app/webui_html/10_overview.html`
- `pythonista_job_runner/app/webui_html/20_jobs.html`
- `pythonista_job_runner/app/webui_html/40_advanced.html`
- `pythonista_job_runner/app/webui_html/45_settings.html` (new)
- `pythonista_job_runner/app/webui_html/50_help.html`
- `pythonista_job_runner/app/webui_css/10_layout.css`
- `pythonista_job_runner/app/webui_css/40_overlays.css`
- `pythonista_job_runner/app/webui_css/50_responsive.css`
- `pythonista_job_runner/app/webui_js/00_core.js`
- `pythonista_job_runner/app/webui_js/10_render_search.js`
- `pythonista_job_runner/app/webui_js/40_events_init.js`
- `pythonista_job_runner/app/webui_build.py`
- `pythonista_job_runner/tests/test_webui_js_regressions.py`
- `pythonista_job_runner/tests/test_webui_mobile_accessibility_and_detail.py`

## Validation commands per milestone

- Milestone 1-2: `cd pythonista_job_runner && python app/webui_build.py --check`, `cd pythonista_job_runner && node --check app/webui.js`
- Milestone 3-4: `cd pythonista_job_runner && pytest -q tests/test_webui_js_regressions.py tests/test_webui_mobile_accessibility_and_detail.py`
- Milestone 5/final: `cd pythonista_job_runner && pytest -q tests/test_webui_*.py`

## Problem-to-implementation checklist

- [x] Jobs subtitle removed.
- [x] Sticky summary row removed.
- [x] Sort control explicitly labeled `Sort`.
- [x] Jobs controls reduced to search/clear/sort + primary filters + collapsed secondary filters.
- [x] Empty state includes clear next step + copyable sample task.
- [x] Help quick start includes Python sample + curl sample + auth + success expectations.
- [x] Dedicated Settings surface exists and owns runtime/UI preferences.
- [x] Advanced reduced to maintenance/rare operations only.
- [x] Queue snapshot visually demoted.
- [x] Passive metadata moved to quiet system details treatment.
- [x] Mobile viewport behavior checked at 320/375/430 and wide sanity.
- [x] Routine polling remains stable/no jobs-table flicker regression.
