Version: 0.6.13-examples.1

# 11_cached_per_job_requirements - Cached per-job requirements

Status: implemented.

## What this example demonstrates

This example is the clean replacement for the older "install into `_deps` every run" mental model. It still uses `dependency_mode: per_job`, but it is designed to be run twice so you can see the add-on reuse package state instead of rebuilding everything on every job.

## Compatibility

This example works on the default lightweight add-on image.

## Files included

- `job_src/run.py`
- `job_src/requirements.txt`
- `job_src/vendor/pjr_demo_formatsize-0.1.0-py3-none-any.whl`
- `job.zip`
- `expected_result/`
- `expected_result.zip`
- `expected_result_manifest.json`

## Add-on settings to use

- **Install requirements.txt automatically**: on
- **Dependency handling mode**: `per_job`
- **Persistent package cache**: on
- **Reuse prepared virtual environments**: on

## How to run

Run the same `job.zip` twice.

The first run will usually create a dependency environment. The second run should normally reuse it. The example itself writes deterministic business outputs, while the add-on result bundle records the package reuse details.

## What to compare between the two runs

Look at these add-on-generated files after each run:

- `package/package_diagnostics.json`
- `summary.txt`
- `result_manifest.json`

The second run should normally show `install_source: reused_venv` or `venv_action: reused` in the package diagnostics.

## Expected stable outputs

- `outputs/cache_probe.json`
- `outputs/summary.md`
- `stdout.txt`
- `stderr.txt`

## Troubleshooting

If both runs still show a full dependency build, check whether reusable virtual environments are disabled, whether the requirements changed between runs, or whether a prune removed the cached environment.
