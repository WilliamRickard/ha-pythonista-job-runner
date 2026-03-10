Version: 6

# Pythonista example runner package

Contents:
- `pythonista_run_example_job.py`
- `example_job_zips/01_hello_world_job.zip`
- `example_job_zips/02_live_logs_progress_job.zip`
- `example_job_zips/03_process_input_files_job.zip`
- `example_job_zips/04_cancel_long_running_job_job.zip`
- `example_job_zips/05_requirements_optional_job.zip`

How to use:
1. Copy the script into Pythonista.
2. Run it.
3. If no saved Home Assistant host or runner token is present, the script prompts once and stores them in the Pythonista keychain under the shared service name `pythonista_job_runner_examples`.
4. Pick either:
   - a direct example `job.zip`
   - the repo zip
   - the top-level bundle zip
5. If the selected zip is not itself runnable, the script searches for embedded example `job.zip` files and lets you choose one.
6. The script saves `submitted.json`, `status.json`, and, when the add-on exposes one, `result.zip` plus `result_extracted/` into a timestamped `runner_results/` subfolder beside the script. That now includes terminal `error` and `cancelled` states as well as `done`.
7. The script also writes a zipped copy of that whole run folder beside it, so each run is easy to share or attach elsewhere.

Recommended validation order:
- `example_job_zips/01_hello_world_job.zip`
- `example_job_zips/02_live_logs_progress_job.zip`
- `example_job_zips/03_process_input_files_job.zip`
- `example_job_zips/04_cancel_long_running_job_job.zip`
- `example_job_zips/05_requirements_optional_job.zip`

Package modes and result artefacts:
- `01` to `04` do not depend on the package subsystem.
- `05_requirements_optional` is the first package-aware example. It still uses `dependency_mode: per_job`, but it expects **Install requirements.txt automatically** to be enabled.
- The dedicated package examples under `examples/packages/` are better run after you have prepared the add-on package settings and any required files under the public add-on config area.
- For package-aware jobs, inspect add-on-generated files such as `package/package_diagnostics.json`, `summary.txt`, `result_manifest.json`, and any exported profile diagnostics alongside the example's own `outputs/` files.

Example 05 now uses a vendored local wheel inside the job zip. With per-job requirements installation enabled, its success path should work without outbound internet access.
