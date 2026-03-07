# Add-on Completion and Expansion Pass

## Current repo state (baseline)
- Add-on already includes ingress streaming (`ingress_stream: true`), custom AppArmor profile (`apparmor.txt`), and constrained runtime flags in `config.yaml`.
- HTTP API already streams upload requests to tempfile and enforces size/content-type checks.
- Audit actor extraction and JSONL persistence exist (`app/audit.py` + `Runner.record_audit_event`).
- Companion integration exists with config flow, polling coordinator, sensors, basic repair issues, system health, and one purge service.
- Existing tests cover API basics, redaction helpers, and static integration checks.

## Workstreams 1-5 verification
### 1. Security hardening and AppArmor
- **Complete enough, with truthful posture**: add-on has non-privileged flags + apparmor profile and ingress/direct API gate logic.
- **Gap to close**: include this in support bundle/docs truthfully without overclaiming confinement guarantees.

### 2. Streamed Ingress uploads
- **Implemented**: ingress stream enabled + streamed temp-file upload in API handler.
- **Gap to close**: include explicit validation evidence in final pass docs.

### 3. Audit trail from ingress identity headers
- **Implemented**: identity extraction from `X-Remote-User-*` gated by ingress proxy IP and persistence to JSONL/job status.
- **Gap to close**: include audit summary in diagnostics/support bundle.

### 4. Companion custom integration
- **Partially complete**: usable baseline exists.
- **Gap to close**: diagnostics implementation, richer service hooks, native event hooks, broader localisation.

### 5. Repairs and System Health
- **Partially complete**: basic repair issue creation and health callback exist.
- **Gap to close**: improve user-facing clarity via diagnostics/support docs and translation surface.

## Workstreams 6-10 scope in this repo
- Add-on support-bundle endpoint with redaction-safe payload.
- Integration diagnostics (`diagnostics.py`) with config-entry diagnostics and redaction.
- Integration automation hooks: refresh/sync + targeted purge services and namespaced job lifecycle events.
- Optional MQTT telemetry publishing from add-on (disabled by default) for job lifecycle/audit actions.
- Localisation expansion for integration strings/services/repairs/diagnostics (English + Spanish baseline).
- Stable vs next/canary release model documentation aligned to repository reality.

## Ordered milestones
1. Baseline inspection + close-out 1-5.
2. Diagnostics + support bundle.
3. Automation hooks.
4. Optional telemetry publishing.
5. Localisation.
6. Stable/next/canary release model docs.
7. Final alignment + validations.

## Expected files to change
- `ADDON_COMPLETION_AND_EXPANSION_PASS.md`
- `pythonista_job_runner/app/http_api_server.py`
- `pythonista_job_runner/app/runner_core.py`
- `pythonista_job_runner/app/support_bundle.py` (new)
- `pythonista_job_runner/config.yaml`
- `pythonista_job_runner/translations/en.yaml`
- `pythonista_job_runner/tests/test_http_api_basic.py`
- `pythonista_job_runner/tests/test_support_bundle.py` (new)
- `custom_components/pythonista_job_runner/{__init__.py,coordinator.py,client.py,services.py,services.yaml,const.py,diagnostics.py,strings.json,translations/en.json,translations/es.json}`
- `tests/test_custom_integration*.py` (expanded)
- `README.md`, `custom_components/pythonista_job_runner/README.md`, `pythonista_job_runner/DOCS.md`, `docs/RELEASE_CHANNELS.md` (new)

## Validation commands per milestone
- Milestone 1: targeted pytest for existing security/upload/audit paths.
- Milestone 2: support bundle + diagnostics tests.
- Milestone 3: integration service/event tests.
- Milestone 4: telemetry unit tests + API behavior tests.
- Milestone 5: translation JSON/YAML parse + integration static tests.
- Milestone 6: markdown link/reference checks.
- Milestone 7: required final gates:
  - `cd pythonista_job_runner && python app/webui_build.py --check`
  - `cd pythonista_job_runner && node --check app/webui.js`
  - `cd pythonista_job_runner && pytest -q`
  - `pytest -q`

## Open decisions
- Telemetry transport selected as MQTT via Home Assistant service call (`mqtt.publish`) through Supervisor API token (no new deps).
- Event model selected as namespaced HA bus events emitted by integration coordinator.

## Capability checklist mapping
- [x] Redacted diagnostics implemented and tested.
- [x] Support bundle implemented, documented includes/excludes, tested.
- [x] Native automation hooks (services + events) implemented and tested.
- [x] Optional MQTT telemetry implemented with safe defaults and tests.
- [x] Localisation expanded beyond English with maintainable structure.
- [x] Stable/next/canary documentation aligned with repository process.
- [x] Final truthfulness sweep complete.


## Final status
- Milestone 1 complete: verified workstreams 1-5 and corrected completeness gaps via diagnostics/automation coverage and updated docs.
- Milestone 2 complete: support bundle endpoint + integration diagnostics with redaction tests.
- Milestone 3 complete: added refresh/cancel/purge services and namespaced job lifecycle events.
- Milestone 4 complete: optional MQTT telemetry (disabled by default), topic prefix config, and test coverage.
- Milestone 5 complete: integration translations expanded to include Spanish baseline and service strings.
- Milestone 6 complete: added release channel documentation (`main` stable, `next` canary).
- Milestone 7 complete: required validation commands pass from checked-in state.
