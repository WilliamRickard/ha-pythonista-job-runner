Version: 0.6.13-examples.3

# 04_cancel_long_running_job - Cancel long-running job

Status: implemented, with completion-path user validation recorded.

## What this example demonstrates

This example is designed to be cancelled while it is still running. It emits a heartbeat once per second, writes partial progress, and handles `SIGTERM` and `SIGINT` so you can test what happens when the Home Assistant Web UI Cancel action is used.

## Compatibility

This example works on the default lightweight add-on image.

## Files included

- `job_src/run.py`
- `job.zip`

## Expected duration

About 90 seconds if you let it run to completion. For the intended test path, start the job and press Cancel after about 10 to 15 seconds.

## How to run from Home Assistant Web UI

Upload `job.zip`, start the job, wait for a few heartbeat lines, then press Cancel. The goal is to confirm that logs remain understandable and that partial output files survive the cancellation.

## How to run from Pythonista

Use `examples/tools/pythonista_run_example_job.py` and select this folder's `job.zip`. This example is better exercised from the Home Assistant Web UI because you can press Cancel there directly.

## Expected logs and outputs

When cancelled, the most useful outputs are:

- `outputs/heartbeat_history.txt`
- `outputs/last_known_progress.json`
- `outputs/cancellation_note.txt`

If you let the job finish instead, it writes `outputs/completed_summary.json`.

## Important note about final state

The exact final state label can depend on how the add-on records external cancellation. The key thing to check is that the job can be interrupted, logs stay readable, and the partial outputs are still useful afterwards.

## Troubleshooting

If cancellation does not leave any partial outputs behind, inspect the add-on process termination path. This example writes progress on each loop iteration so that partial state is always available even if the process is interrupted shortly afterwards.

## Validation evidence

A successful completion-path user run is checked in under `validation_evidence/2026-03-10_pythonista_user_run/`.

The cancellation path is still pending and should be exercised from the Home Assistant Web UI.
