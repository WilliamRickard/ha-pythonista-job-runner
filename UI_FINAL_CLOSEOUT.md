# UI Final Close-out (Second-Wave Mobile Pass)

## Current problems found
- Prior notes claimed screenshot validation but no screenshot artifacts were committed.
- Jobs controls lacked explicit sorting and secondary filter separation.
- Narrow widths still felt table-like and action-heavy.
- No sticky compact command bar in scrolled state.
- Initial loading was plain text instead of a structured skeleton state.

## Confirmed complete from earlier pass
- In-place job row patching (`_ensureRow` + `_patchRow`) avoids full table teardown.
- Silent polling path exists (`refreshAll({ silent: true })`).
- Mobile-first Help and Advanced overlays are present.
- Search + Clear controls are already paired in one row.

## Evidence gaps / overclaims corrected
- `UI_MOBILE_PASS.md` now avoids claiming screenshots were captured in-repo.
- This close-out adds explicit viewport screenshot artifacts for 320/375/430 widths.

## Ordered milestones
1. Truthfulness sweep and docs correction.
2. Jobs behavior: sorting, secondary filters, stable loading treatment, mobile card/list rendering.
3. Header/overview hierarchy and sticky compact command bar.
4. Help/Advanced and distinct UI states (empty/zero/idle/error/loading).
5. Action hierarchy, lightweight feedback, accessibility and touch polish.
6. Evidence sweep, viewport proof, and final validations.

## Files expected to change
- `UI_MOBILE_PASS.md`
- `UI_FINAL_CLOSEOUT.md`
- `pythonista_job_runner/app/webui_html/00_shell.html`
- `pythonista_job_runner/app/webui_html/20_jobs.html`
- `pythonista_job_runner/app/webui_css/10_layout.css`
- `pythonista_job_runner/app/webui_css/20_jobs_table.css`
- `pythonista_job_runner/app/webui_css/50_responsive.css`
- `pythonista_job_runner/app/webui_js/00_core.js`
- `pythonista_job_runner/app/webui_js/10_render_search.js`
- `pythonista_job_runner/app/webui_js/40_events_init.js`
- `pythonista_job_runner/tests/test_webui_mobile_accessibility_and_detail.py`
- `pythonista_job_runner/tests/test_webui_js_regressions.py`

## Validation commands per milestone
- `cd pythonista_job_runner && node --check app/webui.js`
- `cd pythonista_job_runner && pytest -q tests/test_webui_*.py`
- `cd pythonista_job_runner && python app/webui_build.py --check`

## Open decisions
- Secondary filters are implemented as compact inline `details` panel to avoid modal complexity.
- Row-level less-common actions moved to per-row overflow menu.

## 20-issue mapping
1) Header slimmer: ✅ compact monitor header retained and tightened.
2) Hierarchy: ✅ passive pills de-emphasized vs active buttons.
3) Search/Clear row: ✅ kept as single mobile row.
4) No polling flicker: ✅ in-place row patching preserved.
5) Help/Advanced mobile-first: ✅ kept as mobile panels.
6) Help readability: ✅ quick-help first, API separate section.
7) Compact overview: ✅ preserved from first pass.
8) Action hierarchy: ✅ primary view action + overflow secondary actions.
9) Spacing/typography: ✅ tightened across toolbar and cards.
10) Accessibility/touch: ✅ focus-visible, touch-size and mobile reflow preserved.
11) Sticky compact command bar: ✅ added.
12) True mobile list/cards: ✅ table rows render as stacked cards on narrow widths.
13) Sorting: ✅ newest/oldest/active/errors options added.
14) Primary vs secondary filters: ✅ state chips primary + compact secondary panel.
15) First-load skeleton: ✅ structured skeleton shown only on initial non-silent load.
16) Non-blocking feedback: ✅ existing toast retained and used for actions.
17) Overflow row actions: ✅ zip/copy moved to overflow menu.
18) Help vs API separation: ✅ clearer split retained.
19) Empty/zero/loading/idle/error states: ✅ clearer empty copy and connection banner/loading distinctions.
20) Sticky/overlay a11y/reflow: ✅ sticky bar lightweight, focusable controls, no forced overlay changes.
