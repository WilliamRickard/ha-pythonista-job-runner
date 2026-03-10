<!-- Version: 0.6.13-docs.8 -->
# Release readiness checklist

Use this file as the release gate for the dependency-storage and package-management workstream.

## Scope

This checklist covers:

- regression validation of core and package examples
- upgrade validation from earlier `0.6.13` builds
- backup and restore checks for public package inputs
- architecture truthfulness and native-host smoke testing
- changelog and release-note completion

## Automated checks to run before sign-off

1. Run the repository test suite from the repository root with `pytest -q`.
2. Run `pythonista_job_runner/examples/tools/validate_examples.py`.
3. Run `python -m compileall pythonista_job_runner custom_components tests`.
4. Rebuild the bundled Web UI with `pythonista_job_runner/app/webui_build.py` if any part files changed.

## Manual validation matrix

### Core job execution

- [ ] `01_hello_world` still reaches `done` and returns `result.zip`.
- [ ] `02_live_logs_progress` still streams live stdout and stderr in the Web UI.
- [ ] `03_process_input_files` still writes the expected processed outputs.
- [ ] `04_cancel_long_running_job` is explicitly cancelled and records the cancellation path correctly.
- [ ] `05_requirements_optional` covers both the disabled path and the enabled path.

### Package subsystem

- [ ] `11_cached_per_job_requirements` proves warm-cache or warm-venv reuse on a second run.
- [ ] `12_offline_wheelhouse_install` succeeds with local wheelhouse inputs only.
- [ ] `13_named_package_profile_run` succeeds in `profile` mode with the configured default profile.
- [ ] Package cache prune runs without breaking a later reused environment.
- [ ] Package features degrade cleanly when `dependency_mode: disabled`.

### Upgrade and migration

- [ ] Upgrade from an earlier `0.6.13` install that only used per-job `_deps`.
- [ ] Confirm old jobs still run with package features disabled.
- [ ] Confirm package cache and profile settings load without manual migration steps.
- [ ] Confirm profile mode does not silently merge with job-local `requirements.txt`.

### Backup and restore

- [ ] Back up the add-on with files under `/config/package_profiles/` present.
- [ ] Restore to a clean Home Assistant host or test instance.
- [ ] Confirm `/config/package_profiles/` and `/config/wheel_uploads/` restore as expected.
- [ ] Rebuild at least one restored package profile and run one restored offline-wheelhouse job.

### Architecture sign-off

- [ ] `amd64` validated on a real Home Assistant host.
- [ ] `aarch64` validated on a real Home Assistant host.
- [ ] `armv7` validated on a real Home Assistant host.

## Release notes template

Use this structure when you cut the release:

- package subsystem: cache reuse, wheelhouse, reusable virtual environments, package profiles
- Home Assistant integration: package sensors, services, diagnostics, system health
- docs and examples: package examples, migration notes, release-readiness notes
- known limits: no compiled toolchain promises in this release, native-host architecture smoke tests listed explicitly if still pending

## Sign-off record

- Candidate version:
- Test date:
- Tested Home Assistant version:
- Tested architectures:
- Backup and restore checked by:
- Release owner:
- Blocking issues remaining:
