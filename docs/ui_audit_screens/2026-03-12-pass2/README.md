# 2026-03-12 pass2 mobile screenshots

This directory tracks screenshot evidence for pass2 UI audit follow-ups.

Binary screenshots are intentionally **not** committed in this repository because the PR path used for this project may reject binary uploads.

## Typography follow-up screenshot (repro steps)

To regenerate the screenshot that verifies `pythonista_job_runner/app/webui.html` does not render a "Not Found" page:

1. Start a local static server from repo root:
   - `python -m http.server 8000 --directory .`
2. Open `http://127.0.0.1:8000/pythonista_job_runner/app/webui.html` in a browser.
3. Capture and attach the screenshot to the PR description as `webui-typography-fix.png`.

Legacy pass2 captures referenced in prior notes (not present in this repo snapshot):
- `after_jobs_mobile.png`
- `after_detail_mobile.png`
- `after_advanced_mobile.png`
