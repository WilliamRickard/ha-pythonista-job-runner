Version: 0.6.13-examples.3

# Examples tools

This folder contains the support tools for the examples suite.

Files:
- `build_example_zips.py` rebuilds every `job.zip` from `job_src/`
- `validate_examples.py` checks the manifest, folder naming, and required files
- `pythonista_run_example_job.py` is the standalone Pythonista runner script used to submit a selected zip to the add-on
- `manifest_schema.md` documents the manifest structure enforced by the validator
- `pythonista_example_runner_README.md` explains the standalone runner package that is shared to Pythonista users

The Pythonista runner stores the direct API token and Home Assistant host in the Pythonista keychain using the shared service name `pythonista_job_runner_examples`.

After each run the Pythonista runner saves a timestamped run folder under `runner_results/` beside the script and also writes a zipped copy of that full folder beside it.

Package-focused examples usually need add-on configuration or public add-on config files prepared before the job runs. The runner can still submit them, but the example README now tells you which package mode to configure first and which add-on-generated artefacts to inspect afterwards.
