# UI Visual Refinement Pass (Mobile-first)

## Scope and objective
Focused pass to simplify and professionalize the Pythonista Job Runner Web UI on phone widths while preserving backend/API semantics and stable in-place jobs refresh behavior.

## Current clutter and hierarchy problems found
1. Header over-prioritizes metadata pills (version, auto, updated) and action chrome before jobs workflow.
2. Overview card and metadata strip visually compete with Jobs area.
3. Jobs controls are split into multiple mini-systems (search row, control row, sticky row) with mixed hierarchy.
4. Passive and active pills/buttons have similar weight, creating control noise.
5. Job rows expose too many inline affordances and desktop-like table framing on narrow screens.
6. Sticky command bar has moderate visual bulk and weak integration with core jobs commands.
7. Empty/loading/error-ish states are present but not clearly distinguished in language and treatment.
8. Help/Advanced overlays are functional but dense and not strongly mobile-task-oriented.
9. Spacing and alignment rhythm varies between header/cards/toolbar/rows.
10. Accessibility details (focus comfort, long string wrapping, sticky behavior and obscured focus risk) can be tightened.

## What to remove, soften, merge, or restructure
- Remove prominent header pills for low-priority metadata from first-line hierarchy.
- Soften overview and passive metadata visual weight.
- Merge jobs controls into a compact command surface with clear primary/secondary grouping.
- Keep search+clear same row at phone widths (except ultra narrow), with primary state filters immediately available.
- Move secondary filters into a cleaner expandable secondary surface.
- Reduce row action noise with visible high-value action + overflow for secondary actions.
- Tighten sticky command bar spacing, height, and intent.
- Rework state copy and treatment for initial loading vs idle vs no matches vs request failures/disconnect.
- Make Help and Advanced full-screen mobile surfaces with concise task-first sections.

## Ordered milestones
1. Header simplification + hierarchy rebalance toward Jobs.
2. Jobs command system rebuild (search/clear/filters/sort/sticky coherence).
3. Narrow-width jobs presentation and action hierarchy refinement with stable in-place patching.
4. Help/Advanced mobile polish + state treatments + spacing/typography alignment.
5. Accessibility comfort pass + viewport/state evidence + truthfulness sweep.

## Files expected to change
- `pythonista_job_runner/app/webui_html/00_shell.html`
- `pythonista_job_runner/app/webui_html/10_overview.html`
- `pythonista_job_runner/app/webui_html/20_jobs.html`
- `pythonista_job_runner/app/webui_html/40_advanced.html`
- `pythonista_job_runner/app/webui_html/50_help.html`
- `pythonista_job_runner/app/webui_css/10_layout.css`
- `pythonista_job_runner/app/webui_css/20_jobs_table.css`
- `pythonista_job_runner/app/webui_css/40_overlays.css`
- `pythonista_job_runner/app/webui_css/50_responsive.css`
- `pythonista_job_runner/app/webui_js/00_core.js`
- `pythonista_job_runner/app/webui_js/10_render_search.js`
- `pythonista_job_runner/app/webui_js/30_refresh_actions.js`
- `pythonista_job_runner/app/webui_js/40_events_init.js`
- `pythonista_job_runner/app/webui_build.py` (if build logic requires sync)
- `pythonista_job_runner/app/webui.css`, `pythonista_job_runner/app/webui.js`, `pythonista_job_runner/app/webui.html` (generated)
- `pythonista_job_runner/tests/test_webui_*.py`

## Validation commands per milestone
- M1/M2/M3 incremental: `cd pythonista_job_runner && node --check app/webui.js`
- M3/M4 incremental: targeted pytest for modified webui tests.
- Final required:
  - `cd pythonista_job_runner && python app/webui_build.py --check`
  - `cd pythonista_job_runner && pytest -q tests/test_webui_*.py`
  - `cd pythonista_job_runner && node --check app/webui.js`

## Problem-to-implementation checklist
- [x] 1 Header simplification implemented.
- [x] 2 Jobs area dominant over overview/chrome.
- [x] 3 Coherent jobs command system (search/clear/filters/sort/secondary).
- [x] 4 Visual clutter reduction (pills/chips/borders hierarchy).
- [x] 5 Action hierarchy improved (refresh primary, help/advanced secondary, destructive separated, row overflow).
- [x] 6 Narrow-width jobs list/card-like table transformation and scanability.
- [x] 7 Sticky command bar compactness + usability.
- [x] 8 Distinct loading/idle/empty/no-results/error/disconnect treatments.
- [x] 9 Help and Advanced mobile-first polished surfaces.
- [x] 10 Typography/spacing/alignment discipline.
- [x] 11 Accessibility and comfort pass.
- [x] 12 Stable no-flicker in-place jobs updates preserved.

## Progress log
- Started audit and baseline pass.

- Implemented milestone changes in HTML/CSS/JS parts; pending full validation and viewport evidence capture.
