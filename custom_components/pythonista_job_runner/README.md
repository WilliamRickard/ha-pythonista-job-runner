# Pythonista Job Runner custom integration

This integration connects Home Assistant to the Pythonista Job Runner add-on HTTP API.

## Native Home Assistant features
- Config flow + reconfigure flow for endpoint credentials.
- Rich options flow for polling and notification tuning.
- Coordinator-backed sensors for queue and disk metrics.
- Runtime control entities:
  - Number: scan interval
  - Select: notification policy
  - Text: notification target service
- Native button entities for one-shot operational actions:
  - refresh now
  - purge completed jobs
  - purge failed jobs
  - purge all job history
- Update entity showing installed add-on version and latest GitHub release metadata (install is intentionally not supported from this integration).
- Event entities for lifecycle automation surfaces:
  - job_started
  - job_completed
  - job_failed
- Assist intents:
  - running jobs count
  - queue depth
  - refresh status
  - purge completed jobs
- Conservative notify support with throttled failure notifications by default.

## Automation hooks

This integration exposes services for automations:
- `pythonista_job_runner.refresh`
- `pythonista_job_runner.purge_jobs`
- `pythonista_job_runner.purge_done_jobs`
- `pythonista_job_runner.purge_failed_jobs`
- `pythonista_job_runner.cancel_job`

It emits namespaced Home Assistant events from the coordinator:
- `pythonista_job_runner.job_started`
- `pythonista_job_runner.job_completed`
- `pythonista_job_runner.job_failed`
- `pythonista_job_runner.queue_emptied`

## Backup behavior
- Add-on API supports `POST /backup/pause` and `POST /backup/resume` to quiesce new job intake during backups.
- Integration listens for `backup_started` and `backup_ended` events and calls those endpoints when available.
- Backup-agent support is not implemented in this repository because no backup-agent API or SDK wiring exists in the current add-on codebase.

## Diagnostics

Home Assistant diagnostics are implemented in `diagnostics.py` and include integration state plus redacted add-on support-bundle data.
