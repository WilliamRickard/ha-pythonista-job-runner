# Native HA Functionality Pass

## Current repo state (Milestone 1)
- Custom integration exists with config flow, coordinator, sensors, repairs, diagnostics, and a small service set.
- `client.py` had structural issues (duplicate methods and misplaced import) that risk runtime/import failures.
- Reconfigure and options were not clearly separated: reconfigure reused setup logic and setup included tuning fields.
- No update/number/select/text/button/event/notify platforms yet.
- Coordinator emitted only generic job-updated/job-finished events.
- No Assist intent handlers/sentence support.
- Backup-aware pause/restore was not implemented.
- Backup-agent support surface was not present in the repository.

## Workstream status baseline
1. Update entity: missing.
2. Runtime Number/Select/Text: missing.
3. Button entities: missing.
4. Backup-aware pause/restore: missing.
5. Backup-agent support: missing.
6. Reconfigure flow: partial.
7. Richer options flow: partial.
8. Event entities: partial (bus events only).
9. Assist support: missing.
10. Notify support: missing.

## Milestones
1. Baseline inspection + blocker fixes (client cleanup, ownership map, plan).
2. Config-entry UX foundation (real reconfigure flow + richer options).
3. Native control surfaces (update/number/select/text/button).
4. Backup behaviour (pause/resume logic + supportability decision for backup-agent).
5. Automation surfaces (event entities, Assist intents, notify handling).
6. Final alignment (docs/translations/tests/validation + truthfulness sweep).

## Expected files to change
- `NATIVE_HA_FUNCTIONALITY_PASS.md`
- `custom_components/pythonista_job_runner/*.py`
- `custom_components/pythonista_job_runner/translations/*.json`
- `custom_components/pythonista_job_runner/strings.json`
- `custom_components/pythonista_job_runner/manifest.json`
- `custom_components/pythonista_job_runner/README.md`
- `pythonista_job_runner/app/http_api_server.py`
- `pythonista_job_runner/app/runner_core.py`
- `pythonista_job_runner/app/runner/store_lifecycle.py`
- `pythonista_job_runner/tests/*` and `tests/*` additions

## Validation commands per milestone
- M1: `pytest -q tests/test_custom_integration.py tests/test_custom_integration_repairs_health.py`
- M2-M5: targeted `pytest -q tests/test_custom_integration_native_pass.py pythonista_job_runner/tests/test_backup_pause_resume.py`
- M6 final:
  - `cd pythonista_job_runner && python app/webui_build.py --check`
  - `cd pythonista_job_runner && node --check app/webui.js`
  - `cd pythonista_job_runner && pytest -q`
  - `pytest -q tests/test_custom_integration.py tests/test_custom_integration_repairs_health.py tests/test_custom_integration_diagnostics.py tests/test_custom_integration_native_pass.py`

## Open decisions
- Backup-agent support: only implement if a concrete supported API/hook exists in this repo scope; otherwise document as not supportable here.

## Field-ownership map
- Setup flow fields: `base_url`, `token`, `verify_ssl`.
- Reconfigure flow fields: `base_url`, `token`, `verify_ssl` (updates existing entry).
- Options flow fields: `scan_interval`, `create_repairs`, `notify_policy`, `notify_target`, `notify_throttle_seconds`.
- Runtime control entities:
  - Number: `scan_interval`
  - Select: `notify_policy`
  - Text: `notify_target`
- Button entities:
  - `refresh_now`
  - `purge_completed`
  - `purge_failed`
  - `purge_all_history` (maintenance/destructive)

## 10-workstream implementation checklist
- [x] 1 Update entity.
- [x] 2 Number/Select/Text runtime entities.
- [x] 3 Native button entities.
- [x] 4 Backup-aware pause + restore.
- [x] 5 Backup-agent support explicitly limited with rationale.
- [x] 6 Reconfigure flow.
- [x] 7 Rich options flow.
- [x] 8 Event entities.
- [x] 9 Assist intents + utterances.
- [x] 10 Notify support with conservative defaults + suppression.


## Final status (Milestone 6)
- Tier A workstreams implemented with code/tests/docs updates.
- Tier B implemented: add-on backup pause/resume API plus integration backup event listeners.
- Tier C not implemented: backup-agent support is not supportable in this repository state because there is no backup-agent SDK/API wiring or existing integration point to extend safely without inventing unsupported behavior.
- Hassfest attempted via `python -m script.hassfest` but unavailable in this environment (module missing).
