<!-- Version: 0.6.12-webui.2 -->
# Web UI HTML parts

These files are concatenated (in an explicit order defined in `webui_build.py`) to form the body of the Web UI.

Current order:
- `00_shell.html`
- `10_overview.html`
- `20_jobs.html`
- `30_detail.html`
- `40_advanced.html`
- `50_help.html`
- `60_toast.html`

Rules:
- Do not include document-level tags (`<!doctype>`, `<html>`, `<head>`, `<body>`).
- Do not include `<script>` or `<style>` blocks; use `webui_js/*.js` and `webui.css`.
- Avoid root-relative URLs (for example `href="/"`), because Home Assistant Ingress runs under a path prefix.

To rebuild the single-file bundle:
```
python pythonista_job_runner/app/webui_build.py
python pythonista_job_runner/app/webui_build.py --check
```
