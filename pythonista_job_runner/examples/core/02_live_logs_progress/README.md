Version: 0.6.13-examples.3

# 02_live_logs_progress - Live logs and progress

Status: validated.

## What this example demonstrates

This example proves that stdout and stderr stream while the job is still running. It is the first real regression test for the live log view in the Home Assistant Web UI.

## Compatibility

This example works on the default lightweight add-on image.

## Files included

- `job_src/run.py`
- `job.zip`
- `expected_result/`
- `expected_result.zip`
- `expected_result_manifest.json`

## Expected duration

About 8 seconds with the default packaged job. A test-only environment override can reduce the sleep interval for local automated checks.

## How to run from Home Assistant Web UI

Upload `job.zip`, start the job, then stay on the job detail page. You should see one new stdout line each second, with occasional stderr warnings before the job finishes.

## How to run from Pythonista

Use `examples/tools/pythonista_run_example_job.py` and select this folder's `job.zip`.

## Expected logs and outputs

Stable files you can compare against `expected_result/`:

- `outputs/progress_summary.json`
- `outputs/progress_timeline.txt`
- `stdout.txt`
- `stderr.txt`

The full add-on result zip will also include runtime-specific metadata such as timestamps and job IDs.

## What to look for in the UI

The important check is that the logs appear while the job is running, not all at the end. You should also see the stderr warnings interleaved into the live view.

## Troubleshooting

If you only see logs appear at the end, the Web UI or runner tail handling is still broken. Re-test `01_hello_world`, then inspect the latest live-tail code path and the saved `status.json` and `download_attempts.json` from the Pythonista runner.

## Validation evidence

A successful user validation run is checked in under `validation_evidence/2026-03-10_pythonista_user_run/`.
