Version: 2

# Pythonista example runner package

Contents:
- `pythonista_run_example_job.py`
- `example_job_zips/01_hello_world_job.zip`

How to use:
1. Copy the script into Pythonista.
2. Run it.
3. If no saved Home Assistant host or runner token is present, the script prompts once and stores them in the Pythonista keychain under the shared service name `pythonista_job_runner_examples`.
4. Pick either:
   - a direct example `job.zip`
   - the repo zip
   - the top-level bundle zip
5. If the selected zip is not itself runnable, the script searches for embedded example `job.zip` files and lets you choose one.
6. The script saves `submitted.json`, `status.json`, and, when successful, `result.zip` plus `result_extracted/` into a timestamped `runner_results/` subfolder beside the script.

Recommended first run:
- `example_job_zips/01_hello_world_job.zip`
