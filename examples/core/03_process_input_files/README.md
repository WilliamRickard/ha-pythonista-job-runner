Version: 0.6.13-examples.3

# 03_process_input_files - Process input files

Status: validated.

## What this example demonstrates

This example shows that the uploaded job zip can contain bundled input data as well as code. The script reads a small CSV file from the archive, transforms it, and writes multiple outputs under `outputs/`.

## Compatibility

This example works on the default lightweight add-on image.

## Files included

- `job_src/run.py`
- `job_src/data/sample_readings.csv`
- `job.zip`
- `expected_result/`
- `expected_result.zip`
- `expected_result_manifest.json`

## Expected duration

Usually under 10 seconds.

## How to run from Home Assistant Web UI

Upload `job.zip`, start the job, then compare the generated `outputs/processed.csv`, `outputs/summary.md`, and `outputs/stats.json` against the checked-in reference files.

## How to run from Pythonista

Use `examples/tools/pythonista_run_example_job.py` and select this folder's `job.zip`.

## Expected logs and outputs

Stable files you can compare against `expected_result/`:

- `outputs/processed.csv`
- `outputs/summary.md`
- `outputs/stats.json`
- `stdout.txt`
- `stderr.txt`

## Input data model

The bundled CSV contains a small set of timestamped sample readings with a device name and value. The script categorises each reading, calculates totals and averages, and writes both machine-readable and human-readable outputs.

## Troubleshooting

If the script cannot find the CSV file, the job zip was built incorrectly. Rebuild `job.zip` from `job_src/` and check that `data/sample_readings.csv` is present inside the archive.

## Validation evidence

A successful user validation run is checked in under `validation_evidence/2026-03-10_pythonista_user_run/`. That run also exposed a newline mismatch in the earlier checked-in `expected_result/outputs/processed.csv`, which has now been corrected to the Linux add-on output style.
