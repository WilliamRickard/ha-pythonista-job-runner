# Add-on Platform Hardening + Integration Pass

## Current repo state (Milestone 1 baseline)
- Add-on exists under `pythonista_job_runner/` with Ingress-enabled Web UI and direct HTTP API.
- No `apparmor.txt` currently present.
- Add-on config currently exposes host port `8787/tcp` and supports direct API auth via token/CIDR options.
- Upload endpoint `/run` currently requires `Content-Length` and reads entire request body into memory before job creation.
- Job metadata already captures basic Ingress identity headers on submit (`X-Remote-User-*`) when request source IP matches HA ingress proxy.
- No dedicated audit event trail exists for cancel/delete/purge/result-download actions.
- No companion Home Assistant custom integration exists in `custom_components/`.
- Existing pytest suite covers API behavior, runner lifecycle, packaging guardrails, and web UI build guardrails.

## Assumptions confirmed from code
- Runtime job data is stored in `/data/jobs` and add-on options in `/data/options.json`.
- API stats endpoint (`/stats.json`) provides queue/running/done/error and disk usage metrics suitable for integration sensors.
- Ingress auth model is intended to bypass token auth for requests from ingress proxy IP.

## Workstreams
1. Security hardening + custom AppArmor profile
2. Streamed large upload support for Ingress path
3. Audit trail with Ingress identity metadata
4. Companion custom integration
5. Repairs + System Health for integration

## Ordered milestones
1. Baseline inspection and plan ✅
2. Security and AppArmor ✅
3. Streamed uploads ✅
4. Audit trail ✅
5. Companion integration core ✅
6. Repairs and System Health ✅
7. Final alignment and validation ✅

## Files expected to change
- `pythonista_job_runner/config.yaml`
- `pythonista_job_runner/apparmor.txt` (new)
- `pythonista_job_runner/app/http_api_server.py`
- `pythonista_job_runner/app/http_api_auth.py`
- `pythonista_job_runner/app/http_api_helpers.py`
- `pythonista_job_runner/app/runner_core.py`
- `pythonista_job_runner/app/runner/store_lifecycle.py`
- `pythonista_job_runner/app/utils.py`
- `pythonista_job_runner/tests/*` (targeted test additions/updates)
- `custom_components/pythonista_job_runner/*` (new integration)
- `README.md`, `pythonista_job_runner/README.md`, `pythonista_job_runner/DOCS.md`

## Validation commands per milestone
- M1 baseline: targeted file inspection commands (`sed`, `rg`) ✅
- M2 security: `cd pythonista_job_runner && pytest -q tests/test_addon_packaging_guardrails.py`
- M3 uploads: `cd pythonista_job_runner && pytest -q tests/test_http_api_basic.py`
- M4 audit trail: `cd pythonista_job_runner && pytest -q tests/test_http_api_lifecycle_integration.py`
- M5 integration core: `pytest -q tests/test_custom_integration.py` (new root-level test)
- M6 repairs/health: `pytest -q tests/test_custom_integration_repairs_health.py` (new root-level test)
- M7 final gates:
  - `cd pythonista_job_runner && python app/webui_build.py --check`
  - `cd pythonista_job_runner && node --check app/webui.js`
  - `cd pythonista_job_runner && pytest -q`

## Open decisions
- Keep direct host port mapping for backward compatibility vs strict ingress-only default.
- Scope of audit persistence: per-job metadata + global append-only JSONL for non-job actions.
- Integration endpoint defaults (`http://homeassistant.local:8787` vs user-specified host).

## Capability checklist mapping
- [x] Custom AppArmor profile created and referenced by add-on.
- [x] Add-on permissions/settings tightened with least-privilege rationale.
- [x] `ingress_stream` enabled in add-on config.
- [x] Upload handler supports streaming with cancellation/incomplete handling.
- [x] Audit metadata extracted from ingress headers and persisted.
- [x] Audit events include submit/cancel/delete/purge/result-download paths.
- [x] Custom integration with config flow and meaningful status surface.
- [x] Integration translations added for user-facing strings.
- [x] System Health endpoint implemented for integration.
- [x] Repairs issue creation logic implemented and tested.
- [x] Docs aligned with implemented behavior and limitations.
