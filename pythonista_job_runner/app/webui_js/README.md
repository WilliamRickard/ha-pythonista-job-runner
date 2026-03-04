<!-- Version: 0.6.12-webui.8 -->
# Web UI JavaScript parts

The Web UI JavaScript is split into multiple files for readability and review.

The concatenated output is written to `pythonista_job_runner/app/webui.js` by
`pythonista_job_runner/app/webui_build.py`. Do not edit `webui.js` directly.

These files are concatenated in an explicit order defined by `WEBUI_JS_PARTS` in
`pythonista_job_runner/app/webui_build.py`. The build will fail if a file is
missing, or if an unexpected `*.js` file exists in this folder.

Current order:
- `00_core.js`
- `10_render_search.js`
- `20_detail_meta.js`
- `30_refresh_actions.js`
- `40_events_init.js`

Rules:
- Avoid root-relative requests like `fetch('/api')`. Home Assistant Ingress runs
  add-ons under a path prefix, so root-relative URLs typically break.
- If you add a new JS part, update `WEBUI_JS_PARTS` and run:
  - `python pythonista_job_runner/app/webui_build.py`
  - `python pythonista_job_runner/app/webui_build.py --check`
