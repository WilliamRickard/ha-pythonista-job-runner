# S06 Custom Integration Full Review

Scope: merged custom integration core + control/automation surfaces for `custom_components/pythonista_job_runner/*` and directly related tests.

## Section A — Integration core

### S06-H-01 — TLS verification option is ignored by client transport
- **Severity**: High
- **Location**: `custom_components/pythonista_job_runner/client.py` (`RunnerClient._json_get`, `RunnerClient._json_post`)
- **Impact**: `verify_ssl=False/True` in config has no effect because `urlopen` is called without an SSL context; users cannot intentionally disable verification for self-signed endpoints and behavior is inconsistent with exposed option.
- **Recommended fix direction**: pass explicit SSL context into `urlopen`; default context for verify-on, unverified context for verify-off.
- **Test impact**: add targeted unit tests asserting `urlopen(..., context=...)` receives expected context behavior.

### S06-M-01 — Backup event listeners are never unsubscribed
- **Severity**: Medium
- **Location**: `custom_components/pythonista_job_runner/__init__.py` (`async_setup_entry`, `async_unload_entry`)
- **Impact**: Reloads can accumulate backup listeners and duplicate pause/resume calls.
- **Recommended fix direction**: store unsubscribe callbacks and invoke them on unload.
- **Test impact**: add focused test asserting listeners are registered once and unsubscribed on unload.

## Section B — Control and automation surfaces

### S06-M-02 — Service registration exits early when only one service exists
- **Severity**: Medium
- **Location**: `custom_components/pythonista_job_runner/services.py` (`async_register_services`)
- **Impact**: Guarding only on `purge_jobs` can skip registering other services during partial-registration scenarios.
- **Recommended fix direction**: guard each service registration independently.
- **Test impact**: add targeted test with a fake service registry showing missing services are still registered.
