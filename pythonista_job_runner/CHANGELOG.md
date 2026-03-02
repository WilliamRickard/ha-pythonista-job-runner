# Changelog

## Unreleased

## 0.6.6

- Improve add-on presentation in Home Assistant:
  - Add icon.png and logo.png.
  - Add translations for configuration groups and fields (friendly names and descriptions).
  - Reorganise configuration into grouped sections for readability.

## 0.6.5

- Repository scaffold added: CI linting, issue templates, PR checklist.
- Web UI: split source into webui_src.html/webui.css/webui.js with a small bundler (webui_build.py) to regenerate webui.html.
- Web UI: remove inline event handlers and stop using innerHTML for dynamic rows to reduce XSS risk and improve maintainability.
- Web UI: fix tab switching so logs do not go blank (keep per-stream buffers) and cap log growth to avoid runaway memory use.

## 0.6.4

- Fix runner_core syntax error in pip failure handling and restore passing tests.
- Run pip installation as the unprivileged job user (preexec privilege drop).
- Harden result zip creation: skip symlinks and ensure archived files stay within job directories.
- Redact credentials in pip-related errors/notifications; validate pip_trusted_hosts entries.
- Make low-disk cleanup safe and consistent (state cleanup + artefact readiness).
- Keep newest-first job ordering consistent across restarts.
- Wire up install_requirements and pip_* options (per-job pip install into work/_deps, adds to PYTHONPATH).
- Wire up cleanup_min_free_mb (best-effort deletion of oldest finished jobs when disk is low).
- Fix duplicate ip_in_cidrs definition in utils.
- Preserve job ordering across restarts.
- Add CI job to run pytest.
