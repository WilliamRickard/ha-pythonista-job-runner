Version: 0.6.13-examples.6

# Core examples

These examples are intended to work on the default lightweight add-on image.

Current status:
- `01_hello_world`: implemented and user-validated
- `02_live_logs_progress`: user-validated
- `03_process_input_files`: user-validated
- `04_cancel_long_running_job`: completion path user-validated, cancellation path still pending
- `05_requirements_optional`: failure path user-validated, success path still pending, now switched to an offline vendored wheel so the success path no longer depends on PyPI access

Recommended user validation order:
1. `01_hello_world`
2. `02_live_logs_progress`
3. `03_process_input_files`
4. `04_cancel_long_running_job`
5. `05_requirements_optional`

That order starts with the smallest known-good example, then checks live log streaming, bundled input files, cancellation behaviour, and optional dependency installation.

Package-focused follow-up examples now live in `../packages/README.md` rather than the core track. Use those once you want to validate persistent package cache, offline wheelhouse imports, or named package profiles.

Current remaining Phase 2 validation tasks:
1. Run `04_cancel_long_running_job` from the Home Assistant Web UI and press Cancel after several heartbeat lines.
2. Run `05_requirements_optional` again with per-job requirements installation enabled. The example now uses a vendored local wheel, so the success path should not depend on outbound internet access.
