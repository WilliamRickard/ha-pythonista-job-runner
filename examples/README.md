Version: 0.6.13-examples.8

# Pythonista Job Runner examples

This folder is the structured examples area for the add-on.

Phase 1 status:
- scaffold created for all 10 planned examples
- build and validation tools added under `tools/`
- Pythonista runner script added under `tools/`
- example folders are present and each has source, a README, and a built `job.zip`
- `01_hello_world` is implemented, user-validated, and includes checked-in validation evidence

Phase 2 status:
- examples `02_live_logs_progress` to `05_requirements_optional` are now implemented
- examples 02 and 03 are now user-validated and include checked-in validation evidence
- example 03 user validation exposed a newline mismatch in the earlier deterministic CSV reference, which has now been corrected
- example 04 now has checked-in completion-path validation evidence, while the intended cancellation-path validation is still pending
- example 05 now has checked-in failure-path validation evidence, plus deterministic success-path reference artefacts
- example 05 no longer depends on PyPI access for its success path and now uses a vendored local wheel inside the job zip
- the standalone Pythonista runner now zips each saved run folder after the job finishes
- the standalone Pythonista runner now also attempts to download result bundles for terminal `error` and `cancelled` states when the add-on exposes them
- examples 06 to 10 remain to be implemented in later phases

Phase 8 status:
- added a dedicated `packages/` track for package-management workflows
- added `11_cached_per_job_requirements`
- added `12_offline_wheelhouse_install`
- added `13_named_package_profile_run`
- updated docs so the package subsystem has migration notes, example links, and mode-selection guidance
- added package screenshots placeholders for the root README and screenshot contract

Use `tools/build_example_zips.py` to rebuild `job.zip` files from each `job_src/` folder.

Use `tools/validate_examples.py` to check folder naming, manifest consistency, required files, and that cache or compiled files have not been checked into the examples tree.

The examples are split into:
- `core/` for examples intended to run on the default lightweight image
- `packages/` for package-cache, wheelhouse, and package-profile workflows
- `toolchain/` for examples that will require a toolchain-enabled image once implemented

Use `README_TEMPLATE.md` as the structure for per-example documentation.

The Pythonista runner now accepts any of these as the selected zip:
- a direct `job.zip`
- the repo zip that contains many example `job.zip` files
- the top-level bundle zip that contains the repo zip

If the selected zip is not itself runnable, the script will look for embedded example `job.zip` files and let the user choose one before upload.

At the end of each run the script now also writes a zipped copy of the whole run folder beside the folder itself. That zip includes the selected job zip, `submitted.json`, `status.json`, `download_attempts.json`, `result.zip` when present, and `result_extracted/` when extraction succeeded.

When a job ends in `error` or `cancelled`, the script now also tries to download the result bundle if the add-on exposes one, instead of skipping that step outright.
