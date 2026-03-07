<!-- Version: 0.6.12-docs.6 -->
# Changelog

## Unreleased

### Docs

- Clarify the roles of the repository README, add-on README, and full add-on guide.
- Add an "Ingress versus direct API access" section with a concrete Pythonista example.
- Add placeholder screenshots and clearer screenshot replacement guidance.
- Tighten internal Markdown links so the main docs are easier to navigate.

### Web UI build and contributor guidance

- Document the split Web UI source folders and rebuild/check workflow more clearly.
- Add contributor guidance for updating screenshots and avoiding generated artefacts in commits.

### Tests and repo hygiene

- Add a Markdown links test that validates local file targets and section anchors.
- Remove local caches and packaging artefacts from the tracked repo contents.

### API and reliability close-out

- Remove leftover backup artefact `app/runner_core.py.bak` from the tracked repository.
- Refactor HTTP API internals into focused helper modules (`http_api_helpers.py`, `http_api_auth.py`) while preserving route behaviour and response shapes.
- Add regression coverage for runtime error code sanitisation in `/run` and Pythonista client timeout/invalid-JSON handling.

### Architecture claims truthfulness

- Clarify architecture messaging to distinguish declared add-on architectures from what CI runtime tests currently exercise (`amd64`).
- Add docs guardrail tests that fail if this validation-scope note is removed accidentally.

## 0.6.12

- Web UI: fix a JavaScript strict-mode startup error (stray initialTailForJob assignment).
- Web UI: split JavaScript source into pythonista_job_runner/app/webui_js/*.js for maintainability (still bundles to a single ingress-safe webui.html).
- Build: webui_build.py now bundles JS from webui_js/*.js (fallback to webui.js if parts folder is missing).

## 0.6.11

- Web UI: compact job list on mobile (reduce row height, keep key details).
- Web UI: fix job age sorting and display for ISO timestamps.
- Web UI: make Overview tab clearer and hide log controls when viewing Overview.
- Web UI: add Copy job id button and show age/duration/user in the job row on mobile.

## 0.6.10

- Web UI: mobile list-detail navigation (Jobs and Details panes) to reduce clutter.
- Web UI: move polling, auto refresh and purge actions into an Advanced dialog (progressive disclosure).
- Web UI: add Undo to destructive actions (purge, cancel, delete) using delayed execution.
- Web UI: improve typography scale and touch targets; add clearer loading and disconnected states.
- Web UI: add pause and highlight controls for logs, plus quick navigation to the next error.
- Web UI: persist UI settings (filters, search, refresh options, log options) using localStorage.

## 0.6.9

- Web UI: fix Help modal Close button on mobile (improve click and touch handling).
- Web UI: make Help modal typography consistent and improve wording for Quick start and Troubleshooting.

## 0.6.8

- Web UI: add an in-app Help panel with a quick start guide and a human-friendly API endpoint list (copy buttons and curl examples).
- API: add content negotiation for / so browsers get the Web UI while API clients (curl, scripts) get a JSON service index.
- Web UI: improve clipboard behaviour with a fallback for older WebViews.

## 0.6.7

- Web UI: redesigned to be more modern and mobile-friendly (KPI overview cards, clearer controls, and a responsive job list).
- Web UI: fix status indicator and stats display by wiring UI to the current stats.json schema.
- Web UI: add toast notifications for common actions (purge, cancel, delete, copy curl) and better error surfacing.
- Web UI: improve log search performance with debouncing and show match counts.

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
