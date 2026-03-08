# UI Visual Simplification Pass (Mobile-first)

## Current clutter and hierarchy problems found
- Header still competed with itself (title + version + metadata + multiple actions) and repeated refresh control patterns.
- Jobs controls were split into multiple framed rows, with duplicate Refresh in header/jobs/sticky.
- Passive metadata (runner details, retention, storage) was styled similarly to interactive pills.
- Queue snapshot card had strong card framing and high visual weight ahead of Jobs.
- Sticky command bar behaved like a second toolbar instead of a lightweight shortcut.
- Help and Advanced were functionally complete but visually dense for phone use.
- Borders/padding/nested cards created a “compressed dashboard” feel on small screens.

## Removal / merge / soften / demote implementation
- Removed Jobs-toolbar Refresh and sticky Refresh.
- Kept one primary Refresh in header.
- Demoted version into compact System details disclosure metadata.
- Softened passive metadata chips with passive-pill visual treatment.
- Flattened queue snapshot framing and reduced KPI box prominence.
- Merged Jobs controls into one coherent toolbar surface (search+clear, primary filters, compact sort, secondary filters behind one disclosure).
- Kept sticky bar as lightweight search jump + summary context.
- Reduced Help/Advanced visual weight and prioritized quick-start/troubleshooting.

## Ordered milestones (completed)
1. ✅ Header simplification, duplicate refresh removal, passive pill demotion, top-level hierarchy rebalance.
2. ✅ Rebuilt jobs control system and sticky controls into a compact coherent mobile pattern.
3. ✅ Shrunk queue snapshot and increased Jobs dominance; refined empty-state clarity while preserving stable rendering.
4. ✅ Lightened Help/Advanced overlays and tightened spacing/borders/framing globally.
5. ✅ Accessibility and comfort pass, viewport evidence capture, truthfulness sweep, final validations.

## Files changed
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
- `pythonista_job_runner/tests/test_webui_mobile_accessibility_and_detail.py`
- `pythonista_job_runner/tests/test_webui_js_regressions.py`
- generated sync outputs:
  - `pythonista_job_runner/app/webui.html`
  - `pythonista_job_runner/app/webui.css`
  - `pythonista_job_runner/app/webui.js`
- pass notes file:
  - `UI_VISUAL_SIMPLIFICATION_PASS.md`

## Validation commands and results
- ✅ `cd pythonista_job_runner && python app/webui_build.py --check`
- ✅ `cd pythonista_job_runner && node --check app/webui.js`
- ✅ `cd pythonista_job_runner && pytest -q tests/test_webui_*.py` (50 passed)

## Problem-to-implementation checklist
- [x] (1) Header simplified to title + compact connection + one primary refresh; Help/Advanced demoted.
- [x] (2) Duplicate refresh controls removed/demoted.
- [x] (3) Passive metadata pills softened and non-interactive visual treatment applied.
- [x] (4) Queue snapshot reduced in size/weight.
- [x] (5) Jobs controls unified and less layered.
- [x] (6) Sticky controls reduced to minimal utility.
- [x] (7) Jobs becomes visually dominant after top status section.
- [x] (8) Help/Advanced lighter on mobile with quick-start emphasis.
- [x] (9) Spacing, borders, framing tightened globally.
- [x] (10) Accessibility pass for focus, tap comfort, wrapping, non-color cues, no obscured focus.

## Evidence produced
- Screenshot: 320px viewport
- Screenshot: 375px viewport
- Screenshot: 430px viewport
- Screenshot: 1024px sanity viewport
- Regression assertions for:
  - single primary Refresh,
  - coherent jobs toolbar structure,
  - sticky compact behavior,
  - help/advanced mobile surfaces,
  - passive metadata treatment,
  - empty-state messaging for disconnected/filtered/idle.

## Truthfulness sweep
- Claims in this note match implemented source/test changes and executed validation commands.
- No unverified behaviour has been claimed as completed.
