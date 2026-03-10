Version: 0.6.13-examples.4

# 05_requirements_optional - Optional requirements install

Status: implemented, with failure-path user validation recorded.

## What this example demonstrates

This example shows how a job can depend on an extra Python package that is not part of the simplest examples. It uses `requirements.txt` plus a small script that imports the package and writes a human-readable report.

## Compatibility

This example works on the default lightweight add-on image when the add-on is configured to install job requirements.

## Files included

- `job_src/run.py`
- `job_src/requirements.txt`
- `job_src/vendor/pjr_demo_formatsize-0.1.0-py3-none-any.whl`
- `job.zip`
- `expected_result/`
- `expected_result.zip`
- `expected_result_manifest.json`

## Why this example now uses a vendored wheel

The earlier version depended on downloading `humanize` from PyPI at job runtime. That proved brittle in practice because the example success path depended on outbound package access and pip configuration rather than only the add-on feature itself.

This version still tests the same feature, `requirements.txt` installation, but it does so using a small pure-Python wheel that is already bundled inside the job zip. That means the example can prove per-job requirements installation even on systems with no outbound internet access.

## Expected duration

Usually under 10 seconds.

## How to run from Home Assistant Web UI

Enable the setting that installs per-job requirements, then upload `job.zip` and start the job.

You should test both paths:
- with requirements install disabled, confirm the job fails clearly
- with requirements install enabled, confirm the job succeeds and writes the expected outputs

## How to run from Pythonista

Use `examples/tools/pythonista_run_example_job.py` and select this folder's `job.zip`.

## Expected logs and outputs

On success, the key outputs are:

- `outputs/humanized_sizes.json`
- `outputs/summary.md`
- `outputs/requirements_status.json`

On failure because the dependency is missing, the script writes:

- `outputs/requirements_error.json`
- `outputs/next_steps.txt`

and then raises a clear runtime error.

## Troubleshooting

If the job still says the dependency is missing even with requirements install enabled, inspect the add-on requirement installation logs. This example no longer needs outbound package download, so the usual causes are that requirements installation is disabled or pip installation itself failed.

## Validation evidence

A failure-path user run with requirements installation disabled is checked in under `validation_evidence/2026-03-10_pythonista_user_run/`.

A success-path user run with requirements installation enabled is still needed.
