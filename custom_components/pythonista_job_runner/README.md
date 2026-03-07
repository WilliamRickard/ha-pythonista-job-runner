# Pythonista Job Runner custom integration

This integration connects Home Assistant to the Pythonista Job Runner add-on HTTP API.

## Features
- Config flow setup (no YAML required)
- Coordinator-backed sensors for queue and disk metrics
- `pythonista_job_runner.purge_jobs` service
- System Health summary
- Repairs issues for endpoint reachability/auth failures


## Automation hooks

This integration now exposes multiple services for automations:
- `pythonista_job_runner.refresh`
- `pythonista_job_runner.purge_jobs`
- `pythonista_job_runner.purge_done_jobs`
- `pythonista_job_runner.purge_failed_jobs`
- `pythonista_job_runner.cancel_job`

It also emits namespaced Home Assistant events from the coordinator when job states change:
- `pythonista_job_runner.job_updated`
- `pythonista_job_runner.job_finished`

## Diagnostics

Home Assistant diagnostics are implemented in `diagnostics.py` and include integration state plus redacted add-on support-bundle data.
