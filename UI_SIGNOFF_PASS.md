# UI Sign-off Pass (Final Close-out)

## Current close-out problems found
- Generated bundle drift exists: `python app/webui_build.py --check` currently fails because `app/webui.css` is out of date.
- Existing close-out notes contain stale claims that prior passes already captured screenshot evidence; this pass must replace those with evidence actually produced and referenced truthfully.
- Jobs surface is still visually dense on phone widths: many pill/button styles have similar weight and table/card treatment still feels busy.
- Jobs command controls are split across toolbar + sticky row with overlapping responsibility, so command hierarchy feels fragmented.
- Sticky command area currently adds visual weight and duplicate controls instead of acting as a focused quick command rail.

## Stale asset issues found
- `pythonista_job_runner/app/webui.css` is stale relative to source parts (`app/webui_css/*.css`).
- Need to re-run full generator to ensure `app/webui.css`, `app/webui.js`, and `app/webui.html` all align with source parts and version headers.

## Evidence/truthfulness gaps found
- `UI_FINAL_CLOSEOUT.md` currently claims viewport screenshot artifacts were added; this pass verifies evidence references and removes overclaiming.
- `UI_VISUAL_REFINEMENT_PASS.md` progress status is stale and must be updated to reflect real completion evidence only.
- `UI_MOBILE_PASS.md` includes completion assertions that need explicit reconciliation with current checked-in validation state.

## Current clutter/hierarchy problems found
- Header metadata and system-details affordances remain visually competitive with jobs controls.
- Jobs command controls are not visually grouped as one coherent mobile command system.
- Sticky command bar uses too much chrome for low-value duplicated controls.
- Mobile jobs rows still carry extra border/pill noise.
- Empty/loading/disconnected states can be more concise and visually distinct.

## Ordered milestones
1. **Milestone 1**: Repair generated asset drift, regenerate bundle, and make `webui_build.py --check` pass.
2. **Milestone 2**: Truthfulness sweep for UI docs and evidence claims.
3. **Milestone 3**: Visual simplification and jobs-first hierarchy rebalance.
4. **Milestone 4**: Command-system coherence and sticky command cleanup.
5. **Milestone 5**: State polish and Help/Advanced mobile surface refinement.
6. **Milestone 6**: Accessibility and comfort polish.
7. **Milestone 7**: Viewport evidence + full final validation sweep.

## Files expected to change
- `UI_SIGNOFF_PASS.md`
- `UI_FINAL_CLOSEOUT.md`
- `UI_MOBILE_PASS.md`
- `UI_VISUAL_REFINEMENT_PASS.md`
- `pythonista_job_runner/app/webui_html/00_shell.html`
- `pythonista_job_runner/app/webui_html/20_jobs.html`
- `pythonista_job_runner/app/webui_html/40_advanced.html`
- `pythonista_job_runner/app/webui_html/50_help.html`
- `pythonista_job_runner/app/webui_css/10_layout.css`
- `pythonista_job_runner/app/webui_css/20_jobs_table.css`
- `pythonista_job_runner/app/webui_css/40_overlays.css`
- `pythonista_job_runner/app/webui_css/50_responsive.css`
- `pythonista_job_runner/app/webui_js/00_core.js`
- `pythonista_job_runner/app/webui_js/10_render_search.js`
- `pythonista_job_runner/app/webui_js/40_events_init.js`
- `pythonista_job_runner/tests/test_webui_mobile_accessibility_and_detail.py`
- `pythonista_job_runner/tests/test_webui_js_regressions.py`
- generated outputs: `pythonista_job_runner/app/webui.css`, `pythonista_job_runner/app/webui.js`, `pythonista_job_runner/app/webui.html`

## Validation commands by milestone
- M1: `cd pythonista_job_runner && python app/webui_build.py --check`
- M3-M6 incremental: `cd pythonista_job_runner && node --check app/webui.js`
- M3-M6 incremental: `cd pythonista_job_runner && pytest -q tests/test_webui_*.py -k webui`
- M7 final required:
  - `cd pythonista_job_runner && python app/webui_build.py --check`
  - `cd pythonista_job_runner && pytest -q tests/test_webui_*.py`
  - `cd pythonista_job_runner && node --check app/webui.js`

## Close-out checklist mapping
- [x] Generated assets in sync and committed (`webui_build.py --check` passes).
- [x] Truthfulness sweep complete for all UI notes.
- [x] Visual simplification reduces passive chrome/pill noise.
- [x] Jobs surface is dominant and dashboard feel reduced.
- [x] Command system (search/clear/filter/sort/refresh/sticky) coherent on mobile.
- [x] Sticky command bar either clearly helpful or simplified.
- [x] 320/375/430 widths intentionally laid out.
- [x] States polished: loading, idle, no jobs, zero results, disconnected, failure.
- [x] Help/Advanced polished as mobile-first surfaces.
- [x] Accessibility polish: focus, touch target comfort, wrapping/reflow, obscured-focus safety.
- [x] Required validations and evidence captured from checked-in state.

## Progress log
- [x] Initialized sign-off pass document with mandated milestone order and evidence constraints.
- [x] Milestone 1 complete: regenerated assets and passed `webui_build.py --check`.
- [x] Milestone 2 complete: corrected truthfulness claims in close-out notes.
- [x] Milestone 3 complete: simplified visual hierarchy and reduced passive chrome.
- [x] Milestone 4 complete: unified command rows and simplified sticky bar behavior.
- [x] Milestone 5 complete: preserved and polished distinct states and mobile Help/Advanced surfaces.
- [x] Milestone 6 complete: focus/touch/wrapping/sticky-obscure comfort polish verified.
- [x] Milestone 7 complete: viewport artifacts captured (320/375/430/1024) and final validations passed.
