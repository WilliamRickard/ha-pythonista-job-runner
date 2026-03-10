Version: 0.6.13-examples.1

# 07_cpp_compile_and_run - C++ compile and run

Status: scaffold placeholder.

## What this example demonstrates

This folder is in place so the examples suite can be built and validated consistently during Phase 1. The final implementation for this example has not landed yet.

## Compatibility

This example will require the toolchain-enabled add-on image once implemented.

## Files included

- `job_src/run.py`
- `job.zip`

## Expected duration

Under 10 seconds for the Phase 1 scaffold placeholder.

## How to run from Home Assistant Web UI

Upload `job.zip`, start the job, and confirm the scaffold placeholder completes.

## How to run from Pythonista

Use `examples/tools/pythonista_run_example_job.py` and select this folder's `job.zip`.

## Expected logs and outputs

Stdout identifies the example ID and scaffold status. The job writes `outputs/status.txt` and `outputs/details.json`.

## Troubleshooting

If this scaffold placeholder does not run, check the add-on URL, token, and whether the zip was rebuilt after file changes.

## Cleanup notes

The scaffold job creates only small text and JSON outputs.
