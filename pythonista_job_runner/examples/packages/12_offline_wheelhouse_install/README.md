Version: 0.6.13-examples.1

# 12_offline_wheelhouse_install - Offline wheelhouse install

Status: implemented.

## What this example demonstrates

This example proves the public wheelhouse flow. The job zip contains only `requirements.txt` with a package name. The wheel itself is copied into the add-on public config area first, imported into the private wheelhouse, and then installed locally without bundling the wheel inside the job zip.

## Compatibility

This example works on the default lightweight add-on image.

## Files included

- `job_src/run.py`
- `job_src/requirements.txt`
- `public_config/wheel_uploads/pjr_demo_formatsize-0.1.0-py3-none-any.whl`
- `job.zip`
- `expected_result/`
- `expected_result.zip`
- `expected_result_manifest.json`

## Add-on settings to use

- **Install requirements.txt automatically**: on
- **Dependency handling mode**: `per_job`
- **Allow public wheel uploads**: on
- **Prefer local packages before remote indexes**: on

## Setup before running

Copy the wheel from `public_config/wheel_uploads/` into the add-on public config area so it appears under `/config/wheel_uploads/` inside the container.

After that, either let the add-on import it during the next run or open the Packages area and refresh the cache summary first.

## How to run

Upload `job.zip` and start the job.

## What to check in the result bundle

The stable business outputs are deterministic. The important package-specific checks are in add-on-generated files:

- `package/package_diagnostics.json`
- `summary.txt`

You are looking for a local install path such as `install_source: local_wheelhouse`.

## Expected stable outputs

- `outputs/offline_install_status.json`
- `outputs/summary.md`
- `stdout.txt`
- `stderr.txt`

## Troubleshooting

If the import still goes remote, confirm that the wheel was copied into `/config/wheel_uploads/`, that public wheel uploads are enabled, and that the package name in `requirements.txt` matches the wheel metadata.
