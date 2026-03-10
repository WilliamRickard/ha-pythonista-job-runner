Version: 0.6.13-examples.1

# 13_named_package_profile_run - Named package profile run

Status: implemented.

## What this example demonstrates

This example proves `dependency_mode: profile`. The job zip does not carry a `requirements.txt`. Instead, the add-on attaches a named prepared package profile from `/config/package_profiles/`.

## Compatibility

This example works on the default lightweight add-on image.

## Files included

- `job_src/run.py`
- `public_config/package_profiles/demo_formatsize_profile/manifest.json`
- `public_config/package_profiles/demo_formatsize_profile/requirements.txt`
- `public_config/package_profiles/demo_formatsize_profile/README.md`
- `public_config/wheel_uploads/pjr_demo_formatsize-0.1.0-py3-none-any.whl`
- `job.zip`
- `expected_result/`
- `expected_result.zip`
- `expected_result_manifest.json`

## Add-on settings to use

- **Install requirements.txt automatically**: on
- **Dependency handling mode**: `profile`
- **Enable package profiles**: on
- **Default package profile**: `demo_formatsize_profile`
- **Allow public wheel uploads**: on
- **Prefer local packages before remote indexes**: on

## Setup before running

Copy:
- `public_config/package_profiles/demo_formatsize_profile/` into the add-on public config `package_profiles/`
- `public_config/wheel_uploads/pjr_demo_formatsize-0.1.0-py3-none-any.whl` into `wheel_uploads/`

Then either build the profile from the Packages view or let the first run build it on demand.

## How to run

Upload `job.zip` and start the job.

## What to check in the result bundle

The add-on-generated package artefacts should show that the named profile was attached:

- `package/package_diagnostics.json`
- `summary.txt`

You are looking for `profile_name: demo_formatsize_profile` and `install_source: profile_venv`.

## Expected stable outputs

- `outputs/profile_run_status.json`
- `outputs/summary.md`
- `stdout.txt`
- `stderr.txt`

## Troubleshooting

If the job still raises an import error, the add-on is not attaching the profile you think it is. Check the configured default profile name, whether the profile built successfully, and whether the wheel was imported into the local wheelhouse.
