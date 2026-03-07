# Pythonista Job Runner custom integration

This integration connects Home Assistant to the Pythonista Job Runner add-on HTTP API.

## Features
- Config flow setup (no YAML required)
- Coordinator-backed sensors for queue and disk metrics
- `pythonista_job_runner.purge_jobs` service
- System Health summary
- Repairs issues for endpoint reachability/auth failures
