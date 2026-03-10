Version: 0.6.13-examples.1

# Examples tools

This folder contains the support tools for the examples suite.

Files:
- `build_example_zips.py` rebuilds every `job.zip` from `job_src/`
- `validate_examples.py` checks the manifest, folder naming, and required files
- `pythonista_run_example_job.py` is the standalone Pythonista runner script used to submit a selected zip to the add-on
- `manifest_schema.md` documents the manifest structure enforced by the validator

The Pythonista runner stores the direct API token and Home Assistant host in the Pythonista keychain using the shared service name `pythonista_job_runner_examples`.
