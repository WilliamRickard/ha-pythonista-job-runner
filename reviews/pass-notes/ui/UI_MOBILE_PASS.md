Version: 0.6.12-ui-mobile-pass.1
# UI Mobile-First Improvement Pass (Pythonista Job Runner)

Current location: `reviews/pass-notes/ui/UI_MOBILE_PASS.md`

## Current problems found
- Header consumed too much vertical space with similarly styled pills competing with primary actions.
- Jobs refresh rebuilt table body each poll (`tbody.textContent = ""`), causing visible flicker and selection/focus instability.
- Jobs toolbar wrapped awkwardly on mobile (search/clear and filters lacked a compact mobile pattern).
- Jobs region changed height significantly across loading/empty/populated states.
- Help and Advanced overlays used desktop-centered modal geometry on phone widths.
- Help API section was dense on mobile with repetitive copy actions and long content blocks.
- Overview KPI card was larger than needed on narrow screens.
- Action hierarchy between Refresh, utility actions, and destructive actions was weak.
- Spacing/type rhythm and passive-vs-active affordances needed stronger consistency.
- Accessibility needed focused improvements around focus visibility, touch comfort, and long-string safety.

## Ordered milestones
1. **Jobs stability first**: in-place job row patching, silent polling, mobile search/clear/filter toolbar, stable jobs region height.
2. **Header + overview compression**: reduce chrome and metadata prominence; stronger passive badge styles.
3. **Help + Advanced mobile-first surfaces**: full-screen/sheet-like behavior, simpler help section layout.
4. **Action hierarchy + spacing/type discipline**: clearer primary/secondary/destructive grouping.
5. **Accessibility and polish**: focus/touch/wrapping/larger-text checks; truthfulness sweep and final validation.

## Files expected to change
- `UI_MOBILE_PASS.md`
- `pythonista_job_runner/app/webui_html/00_shell.html`
- `pythonista_job_runner/app/webui_html/10_overview.html`
- `pythonista_job_runner/app/webui_html/20_jobs.html`
- `pythonista_job_runner/app/webui_html/40_advanced.html`
- `pythonista_job_runner/app/webui_html/50_help.html`
- `pythonista_job_runner/app/webui_css/10_layout.css`
- `pythonista_job_runner/app/webui_css/20_jobs_table.css`
- `pythonista_job_runner/app/webui_css/40_overlays.css`
- `pythonista_job_runner/app/webui_css/50_responsive.css`
- `pythonista_job_runner/app/webui_js/10_render_search.js`
- `pythonista_job_runner/app/webui_js/30_refresh_actions.js`
- `pythonista_job_runner/tests/test_webui_mobile_accessibility_and_detail.py`
- `pythonista_job_runner/tests/test_webui_js_regressions.py`

## Validation commands per milestone
1. `cd pythonista_job_runner && pytest -q tests/test_webui_js_regressions.py`
2. `cd pythonista_job_runner && pytest -q tests/test_webui_mobile_accessibility_and_detail.py`
3. `cd pythonista_job_runner && python app/webui_build.py --check`
4. `cd pythonista_job_runner && pytest -q tests/test_webui_*.py`

## Open decisions
- Advanced panel on phones implemented as full-screen panel (simpler than bottom sheet in current architecture).
- API list retains copy actions only for core endpoints; non-core endpoints remain visible but non-interactive.

## 10-issue checklist mapping
- [x] 1. Monitoring header compressed and metadata de-emphasized.
- [x] 2. Visual hierarchy strengthened for passive badges vs interactive controls.
- [x] 3. Jobs toolbar mobile row + horizontally scrollable filters.
- [x] 4. Jobs flicker/layout jump fixed with silent in-place polling updates.
- [x] 5. Help/Advanced mobile-first surfaces.
- [x] 6. Help content simplified into quick start / API / troubleshooting mobile scan.
- [x] 7. Overview compacted.
- [x] 8. Action hierarchy and destructive grouping clarified.
- [x] 9. Spacing/typography system tightened.
- [x] 10. Accessibility pass (focus, touch targets, wrapping, non-color cues).


## Milestone completion notes
- Milestone 1 complete: in-place jobs row patching, silent polling, stable jobs region, mobile toolbar row and filter scroller.
- Milestone 2 complete: compact monitoring header, condensed overview, passive metadata badges.
- Milestone 3 complete: help/advanced mobile panels and denser help API presentation.
- Milestone 4 complete: clearer primary/secondary/destructive action styling and grouping.
- Milestone 5 complete: focus-visible, touch target consistency, wrapping safeguards, validation. (No screenshot artifacts were committed in this document.)
