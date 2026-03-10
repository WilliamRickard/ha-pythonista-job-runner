Version: 0.6.13-examples.1

# Package examples

These examples are aimed at the persistent package subsystem rather than the base job contract.

They cover three distinct workflows:
- `11_cached_per_job_requirements`: run the same job twice in `per_job` mode and inspect package reuse diagnostics
- `12_offline_wheelhouse_install`: import a wheel into the public wheelhouse, then install it without bundling the wheel inside the job zip
- `13_named_package_profile_run`: prepare a named package profile once, then run a job in `profile` mode with no job-local `requirements.txt`

Recommended validation order:
1. `11_cached_per_job_requirements`
2. `12_offline_wheelhouse_install`
3. `13_named_package_profile_run`

These examples are not bundled into the small Pythonista runner package by default because each one needs add-on package settings or public add-on config files prepared first.

The stable result files for these examples live under each example's `expected_result/` folder. The full add-on result bundle will also include package artefacts such as `package/package_diagnostics.json`, `package/pip_install_report.json`, and `result_manifest.json` when the add-on generated them.
