Version: 0.6.13-examples.3

# Pythonista Job Runner examples

This folder is the structured examples area for the add-on.

Phase 1 status:
- scaffold created for all 10 planned examples
- build and validation tools added under `tools/`
- Pythonista runner script added under `tools/`
- example folders are present and each has source, a README, and a built `job.zip`
- `01_hello_world` is implemented, user-validated, and now includes checked-in validation evidence
- examples 02 to 10 remain to be implemented in later phases

Use `tools/build_example_zips.py` to rebuild `job.zip` files from each `job_src/` folder.

Use `tools/validate_examples.py` to check folder naming, manifest consistency, and required files.

The examples are split into:
- `core/` for examples intended to run on the default lightweight image
- `toolchain/` for examples that will require a toolchain-enabled image once implemented

Use `README_TEMPLATE.md` as the structure for per-example documentation.

The Pythonista runner now accepts any of these as the selected zip:
- a direct `job.zip`
- the repo zip that contains many example `job.zip` files
- the top-level bundle zip that contains the repo zip

If the selected zip is not itself runnable, the script will look for embedded example `job.zip` files and let the user choose one before upload.
