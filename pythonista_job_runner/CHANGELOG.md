<!-- Version: 0.6.16-docs.1 -->
# Changelog

## 0.6.16

- Fixed the header More menu on iPhone and Home Assistant WebView so a touch no longer opens and then immediately closes the menu because of a follow-up synthetic click.
- Added Web UI regression coverage for the touch or pointer activation path to keep the More menu from regressing again.

## Unreleased

### Package subsystem and release readiness

- Add a persistent package subsystem covering pip cache reuse, offline-first wheelhouse imports, reusable keyed virtual environments, named package profiles, package cache pruning, and Home Assistant integration sensors and service actions.
- Add package-focused examples for cached per-job requirements, offline wheelhouse installs, and named package profile runs.
- Add release-readiness documentation covering regression validation, upgrade checks, backup and restore checks for package profiles, and native-host sign-off.


### Web UI and add-on usability

- Fix the header `More` dropdown staying visible because `.header-more-panel` used `display:grid`, which overrides the HTML `hidden` attribute unless CSS explicitly restores `display:none` for the hidden state.
- Add regression tests that require the header menu to keep the `hidden` attribute in markup and a matching `.header-more-panel[hidden]{display:none !important;}` rule in both source and built assets.

- Fix a Web UI JavaScript syntax error in the job detail package metadata renderer that stopped the entire Ingress UI from responding after the script failed to parse.
- Add a regression check that syntax-checks the bundled `webui.js` file and verifies the `Package find-links` newline join is emitted correctly.

- Add a guided Setup flow in the Web UI for profile-mode package examples, including readiness checks, wheel uploads, profile archive uploads, delete and replace actions, build and rebuild controls, restart guidance, and a suggested config snippet.
- Document the new Setup workflow in the repository README, add-on guide, package examples, and release-readiness checklist.
- Extend automated checks with an end-to-end setup-flow API test that uploads files, builds the target profile, and verifies the ready state without a live Home Assistant host.
- Fix live stdout and stderr streaming so the Web UI updates during execution instead of waiting for large buffered reads or job completion.
- Replace new-tab stdout, stderr, and result downloads with in-page authenticated fetch downloads so Home Assistant Ingress sessions do not fail with `401 Unauthorized` in Safari or external browser handoff.
- Show the active Home Assistant host at the top of the Web UI and surface direct-access mode plus configured allowed CIDRs in System details.
- Tidy header and action alignment, including the Queue summary row and detail action buttons.
- Rewrite add-on option labels and helper text in `translations/en.yaml`, remove the stale `bind_port` translation entry, and add CIDR examples for iPhone-only and whole-LAN access.

## 0.6.12

### Docs

- Rework the repository [`README.md`](../README.md) into a shorter landing page with a clearer install path and docs map.
- Rework [`README.md`](README.md) into a tighter store-facing add-on summary that points detail back to [`DOCS.md`](DOCS.md).
- Rebuild [`DOCS.md`](DOCS.md) around task-based sections for install, first run, security, troubleshooting, and API usage.
- Tighten [`SECURITY.md`](../SECURITY.md) so the safe default operating model and trust boundaries are easier to follow.
- Tidy [`docs/RELEASE_CHANNELS.md`](../docs/RELEASE_CHANNELS.md) and [`docs/screenshots/README.md`](../docs/screenshots/README.md).
- Add GitHub community-facing docs and forms with [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) plus support and docs-feedback issue forms.
- Move UI pass-note Markdown files out of the repository root and into [`../reviews/pass-notes/ui/`](../reviews/pass-notes/ui/).

### Web UI build and contributor guidance

- Document the split Web UI source folders and rebuild/check workflow more clearly.
- Add contributor guidance for updating screenshots and avoiding generated artefacts in commits.

### Tests and repo hygiene

- Expand docs guardrail coverage to include more user-facing Markdown files.
- Remove user-facing root-level clutter by relocating review pass notes under [`../reviews/pass-notes/ui/`](../reviews/pass-notes/ui/).

### API and reliability close-out

- Remove leftover backup artefact `app/runner_core.py.bak` from the tracked repository.
- Refactor HTTP API internals into focused helper modules (`http_api_helpers.py`, `http_api_auth.py`) while preserving route behaviour and response shapes.
- Add regression coverage for runtime error code sanitisation in `/run` and Pythonista client timeout and invalid-JSON handling.

### Architecture claims truthfulness

- Clarify architecture messaging to distinguish declared add-on architectures from what continuous integration runtime tests currently exercise (`amd64`).
- Add docs guardrail tests that fail if this validation-scope note is removed accidentally.

## 0.6.12

- Web UI: fix a JavaScript strict-mode startup error (stray initialTailForJob assignment).
- Web UI: split JavaScript source into `pythonista_job_runner/app/webui_js/*.js` for maintainability while still bundling to a single Ingress-safe `webui.html`.
- Build: `webui_build.py` now bundles JavaScript from `webui_js/*.js`, with fallback to `webui.js` if the parts folder is missing.

## 0.6.11

- Web UI: compact job list on mobile and reduce row height while keeping key details.
- Web UI: fix job age sorting and display for ISO timestamps.
- Web UI: make the Overview tab clearer and hide log controls when viewing Overview.
- Web UI: add Copy job id and show age, duration, and user in the job row on mobile.

## 0.6.10

- Web UI: mobile list-detail navigation to reduce clutter.
- Web UI: move polling, auto refresh, and purge actions into an Advanced dialog.
- Web UI: add Undo to destructive actions using delayed execution.
- Web UI: improve typography scale and touch targets, and add clearer loading and disconnected states.
- Web UI: add pause and highlight controls for logs, plus quick navigation to the next error.
- Web UI: persist UI settings using local storage.
